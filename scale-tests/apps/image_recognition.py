#
## The following is an example taken from Databricks: https://docs.databricks.com/applications/deep-learning/spark-integration.html
# This runs TensorFlow on Spark with GPUs

import numpy as np
import os
import os.path
import re
import tarfile
import tensorflow as tf
from pyspark.sql import SparkSession
from subprocess import Popen, PIPE, STDOUT
from tensorflow.python.platform import gfile


class NodeLookup(object):
  """Converts integer node IDs to human readable labels."""

  def __init__(self,
               label_lookup_path=None,
               uid_lookup_path=None):
    if not label_lookup_path:
      label_lookup_path = os.path.join(
          model_dir, 'imagenet_2012_challenge_label_map_proto.pbtxt')
    if not uid_lookup_path:
      uid_lookup_path = os.path.join(
          model_dir, 'imagenet_synset_to_human_label_map.txt')
    self.node_lookup = self.load(label_lookup_path, uid_lookup_path)

  def load(self, label_lookup_path, uid_lookup_path):
    """Loads a human readable English name for each softmax node.

    Args:
      label_lookup_path: string UID to integer node ID.
      uid_lookup_path: string UID to human-readable string.

    Returns:
      dict from integer node ID to human-readable string.
    """
    if not gfile.Exists(uid_lookup_path):
      tf.logging.fatal('File does not exist %s', uid_lookup_path)
    if not gfile.Exists(label_lookup_path):
      tf.logging.fatal('File does not exist %s', label_lookup_path)

    # Loads mapping from string UID to human-readable string
    proto_as_ascii_lines = gfile.GFile(uid_lookup_path).readlines()
    uid_to_human = {}
    p = re.compile(r'[n\d]*[ \S,]*')
    for line in proto_as_ascii_lines:
      parsed_items = p.findall(line)
      uid = parsed_items[0]
      human_string = parsed_items[2]
      uid_to_human[uid] = human_string

    # Loads mapping from string UID to integer node ID.
    node_id_to_uid = {}
    proto_as_ascii = gfile.GFile(label_lookup_path).readlines()
    for line in proto_as_ascii:
      if line.startswith('  target_class:'):
        target_class = int(line.split(': ')[1])
      if line.startswith('  target_class_string:'):
        target_class_string = line.split(': ')[1]
        node_id_to_uid[target_class] = target_class_string[1:-2]

    # Loads the final mapping of integer node ID to human-readable string
    node_id_to_name = {}
    for key, val in node_id_to_uid.items():
      if val not in uid_to_human:
        tf.logging.fatal('Failed to locate: %s', val)
      name = uid_to_human[val]
      node_id_to_name[key] = name

    return node_id_to_name

  def id_to_string(self, node_id):
    if node_id not in self.node_lookup:
      return ''
    return self.node_lookup[node_id]

# Helper methods for reading images

def run(cmd):
  p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
  return p.stdout.read()

def read_file_index(images_read_limit, image_batch_size):
  from six.moves import urllib

  IMAGES_INDEX_URL = 'http://image-net.org/imagenet_data/urls/imagenet_fall11_urls.tgz'

  content = urllib.request.urlopen(IMAGES_INDEX_URL)
  data = content.read(images_read_limit)
  tmpfile = "/tmp/imagenet.tgz"
  with open(tmpfile, 'wb') as f:
    f.write(data)
  run("tar -xOzf %s > /tmp/imagenet.txt" % tmpfile)
  with open("/tmp/imagenet.txt", 'r') as f:
    lines = [l.split() for l in f]
    input_data = [tuple(elts) for elts in lines if len(elts) == 2]
    return [input_data[i:i+image_batch_size] for i in range(0,len(input_data), image_batch_size)]


# Distributed image processing: Tensorflow on Spark
def run_inference_on_image(sess, img_id, img_url, node_lookup):
    """Download an image, and run inference on it.

    Args:
      image: Image file URL

    Returns:
      (image ID, image URL, scores),
      where scores is a list of (human-readable node names, score) pairs
    """
    from six.moves import urllib

    try:
        image_data = urllib.request.urlopen(img_url, timeout=1.0).read()
    except:
        return (img_id, img_url, None)

    # Some useful tensors:
    # 'softmax:0': A tensor containing the normalized prediction across
    #   1000 labels.
    # 'pool_3:0': A tensor containing the next-to-last layer containing 2048
    #   float description of the image.
    # 'DecodeJpeg/contents:0': A tensor containing a string providing JPEG
    #   encoding of the image.
    # Runs the softmax tensor by feeding the image_data as input to the graph.
    softmax_tensor = sess.graph.get_tensor_by_name('softmax:0')
    try:
        predictions = sess.run(softmax_tensor,
                               {'DecodeJpeg/contents:0': image_data})
    except:
        # Handle problems with malformed JPEG files
        return (img_id, img_url, None)
    print(predictions)
    predictions = np.squeeze(predictions)

    num_top_predictions = 5
    top_k = predictions.argsort()[-num_top_predictions:][::-1]
    scores = []
    for node_id in top_k:
        if node_id not in node_lookup:
            human_string = ''
        else:
            human_string = node_lookup[node_id]
        score = predictions[node_id]
        scores.append((human_string, score))
    return (img_id, img_url, scores)


def apply_inference_on_batch(batch):
    """Apply inference to a batch of images.

    We do not explicitly tell TensorFlow to use a GPU.
    It is able to choose between CPU and GPU based on its guess of which will be faster.
    """
    with tf.Graph().as_default():
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(model_data_bc.value)
        tf.import_graph_def(graph_def, name='')
        with tf.Session(config=tf.ConfigProto(log_device_placement=True)) as sess:
            labeled = [run_inference_on_image(sess, img_id, img_url, node_lookup_bc.value) for (img_id, img_url) in
                       batch]
            return [tup for tup in labeled if tup[2] is not None]


if __name__ == "__main__":
    import sys

    MODEL_URL = 'http://download.tensorflow.org/models/image/imagenet/inception-2015-12-05.tgz'
    model_dir = '/tmp/imagenet'

    spark = SparkSession \
        .builder \
        .appName("GPU Image Recognition") \
        .getOrCreate()

    # Download the model
    def maybe_download_and_extract():
        """Download and extract model tar file."""
        from six.moves import urllib
        dest_directory = model_dir
        if not os.path.exists(dest_directory):
            os.makedirs(dest_directory)
        filename = MODEL_URL.split('/')[-1]
        filepath = os.path.join(dest_directory, filename)
        if not os.path.exists(filepath):
            filepath2, _ = urllib.request.urlretrieve(MODEL_URL, filepath)
            print("filepath2", filepath2)
            statinfo = os.stat(filepath)
            print('Succesfully downloaded', filename, statinfo.st_size, 'bytes.')
            tarfile.open(filepath, 'r:gz').extractall(dest_directory)
        else:
            print('Data already downloaded:', filepath, os.stat(filepath))

    maybe_download_and_extract()

    # Load model data
    model_path = os.path.join(model_dir, 'classify_image_graph_def.pb')
    with gfile.FastGFile(model_path, 'rb') as f:
      model_data = f.read()

    sc = spark.sparkContext
    model_data_bc = sc.broadcast(model_data)

    node_lookup = NodeLookup().node_lookup
    # Broadcast node lookup table to use on Spark workers
    node_lookup_bc = sc.broadcast(node_lookup)

    if len(sys.argv) > 1:
        images_read_limit = int(sys.argv[1])
        image_batch_size = int(sys.argv[2])
        print("read limit: {}, batch size: {}".format(images_read_limit, image_batch_size))
    else:
        images_read_limit = 1000
        image_batch_size = 3

    batched_data = read_file_index(images_read_limit, image_batch_size)
    print("There are %d batches" % len(batched_data))

    # Run Spark!
    urls = sc.parallelize(batched_data)
    labeled_images = urls.flatMap(apply_inference_on_batch)
    local_labeled_images = labeled_images.collect()
    print("Final result: ", local_labeled_images)



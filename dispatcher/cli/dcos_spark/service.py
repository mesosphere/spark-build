from dcos import config


def app_id():
    try:
        return config.get_config()["spark.app_id"]
    except KeyError:
        return "spark"


def set_app_id(app_id):
    config.set_val("spark.app_id", app_id)

package org.apache.spark.metrics.sink.statsd;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.SocketException;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * An simple UDP server that makes received datagram packets available as strings.
 */
public class DatagramTestServer implements Runnable, AutoCloseable {

    private volatile boolean mustStop = false;
    private byte[] buf = new byte[256];
    private List<String> messages = new CopyOnWriteArrayList();
    private DatagramSocket socket;

    private DatagramTestServer(int port) throws SocketException {
        socket = new DatagramSocket(port);
    }

    /**
     * Stops the thread
     * @throws SocketException
     */
    @Override
    public void close() throws SocketException {
        mustStop = true;
        socket.close();
    }

    @Override
    public void run() {
        while (!mustStop) {
            DatagramPacket packet  = new DatagramPacket(buf, buf.length);
            try {
                socket.receive(packet);
                String message = new String(packet.getData(), 0, packet.getLength());
                messages.add(message);
            } catch (IOException e) {
                // ignore socket closed exception
            }
        }
    }

    public List<String> receivedMessages() {
        return messages;
    }

    public static DatagramTestServer run(int port) throws SocketException {
        DatagramTestServer server = new DatagramTestServer(port);
        Thread thread = new Thread(server);
        thread.start();
        return server;
    }
}

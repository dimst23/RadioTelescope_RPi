from PyQt5 import QtCore, QtNetwork
import logData_Pi


class TCPServer(QtCore.QObject):
    # Create the signals to be used for data handling
    sendDataClient = QtCore.pyqtSignal(str, name='clientDataSend')  # Send the data to Stellarium

    def __init__(self, cfg, parent=None):
        super(TCPServer, self).__init__(parent)  # Get the parent of the class
        self.port = cfg.getPort()  # Get the server port from the settings file
        self.log_data = logData_Pi.logData(__name__)  # Create the necessary logger

    # This method is called in every thread start
    def start(self):
        self.socket = None  # Create the instance os the socket variable to use it later
        self.connectServ()  # Start the Stellarium server

    @QtCore.pyqtSlot(name='reConnectStell')
    def connectServ(self):
        # Get the saved data from the settings file
        self.host = self.cfgData.getStellHost()  # Get the TCP connection host
        self.port = self.cfgData.getStellPort()  # Get the TCP connection port

        if self.host == "localhost":
            self.host = QtNetwork.QHostAddress.LocalHost
        else:
            for ipAddress in QtNetwork.QNetworkInterface.allAddresses():
                if ipAddress != QtNetwork.QHostAddress.LocalHost and ipAddress.toIPv4Address() != 0:
                    break
                else:
                    ipAddress = QtNetwork.QHostAddress.LocalHost
            self.host = ipAddress  # Save the local IP address

        self.tcpServer = QtNetwork.QTcpServer()  # Create a server object
        self.tcpServer.newConnection.connect(self.new_connection)  # Handler for a new connection
        self.sendDataStell.connect(self.send)  # Connect the signal trigger for data sending

        self.tcpServer.listen(QtNetwork.QHostAddress(self.host), int(self.port))  # Start listening for connections
        self.conStatSigS.emit("Waiting")  # Indicate that the server is listening on the GUI

    # Whenever there is new connection, we call this method
    def new_connection(self):
        if self.tcpServer.hasPendingConnections():
            self.socket = self.tcpServer.nextPendingConnection()  # Returns a new QTcpSocket

            if self.socket.state() == QtNetwork.QAbstractSocket.ConnectedState:
                self.conStatSigS.emit("Connected")  # Indicate that the server has a connection on the GUI
                self.socket.readyRead.connect(self._receive)  # If there is pending data get it
                self.socket.disconnected.connect(self._disconnected)  # Execute the appropriate code on state change
                self.tcpServer.close()  # Stop listening for other connections

    # Should we have data pending to be received, this method is called
    def _receive(self):
        try:
            if self.socket.bytesAvailable() > 0:
                recData = self.socket.readAll().data().decode('utf-8')  # Get the data as a string
        except Exception:
            # If data is sent fast, then an exception will occur
            self.logD.log("EXCEPT", "A connected client abruptly disconnected. Returning to connection waiting")

    # If at any moment the connection state is changed, we call this method
    def _disconnected(self):
        # Do the following if the connection is lost
        self.tcpServer.listen(QtNetwork.QHostAddress(self.host), int(self.port))  # Start listening again

    # This method is called whenever the signal to send data back is fired
    @QtCore.pyqtSlot(str, name='clientDataSend')
    def send(self, data: str):
        try:
            if self.socket.state() == QtNetwork.QAbstractSocket.ConnectedState:
                self.socket.write(data.encode('utf-8'))  # Send data back to client
                self.socket.waitForBytesWritten()  # Wait for the data to be written
        except Exception:
            self.logD.log("EXCEPT", "Problem sending data. See traceback.", "send")

    def releaseClient(self):
        self.socket.close()

    # This method is called whenever the thread exits
    def close(self):
        if self.socket is not None:
            self.socket.disconnected.disconnect()  # Close the disconnect signal first to avoid firing
            self.socket.close()  # Close the underlying TCP socket
        self.tcpServer.close()  # Close the TCP server
        self.sendDataStell.disconnect()  # Detach the signal to avoid any accidental firing (Reconnected at start)
        self.reConnectSigS.disconnect()  # Not needed any more since we are closing

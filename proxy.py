#!/usr/bin/env python3

import bitarray
import email
import email.policy
import os
import socket
import struct
import sys
import threading

maxRecvSize = 4096
browserEncScheme = 'utf-8'
proxyEncScheme = 'utf-8'
policy = email.policy.compat32.clone(linesep='\r\n')
otherIP = None
otherPort = None
serverMode = False


'''
Logic for the browser-side proxy
'''
def processBrowser(conn, client):
    # get message and convert it to bit representation
    message = input("Enter message to send: ")
    bits = bitarray.bitarray()
    bits.frombytes(message.encode(proxyEncScheme))

    try:
        # open connection to other proxy
        sOther = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sOther.connect((otherIP, otherPort))

        # loop until entire covert message is sent
        messageSent = False
        while not messageSent:
            # receive request from browser
            request = conn.recv(maxRecvSize).decode(browserEncScheme)

            # insert covert message, determine if message incomplete
            modifiedReq, messageSent = modifyCase(request, bits)
            if not messageSent:
                print(str(bits.length()) + " bits remaining;" +
                        " please send additional request.")

            # send modified request to other proxy
            sOther.send(modifiedReq.encode(proxyEncScheme))

            responseBits = bitarray.bitarray()
            eofFound = False
            # loop until entire covert message received
            while not eofFound:
                # receive response from other proxy
                response = sOther.recv(maxRecvSize)
                if (len(response) == 0):
                    break

                top, crlf, body = response.partition(b'\x0D\x0A\x0D\x0A')
                top = top.decode(proxyEncScheme)

                # extract covert message, determine if message incomplete
                eofFound = interpretCase(top, responseBits)
                if eofFound:
                    extractMessage(responseBits)
                    # forward the message to the browser
                    response = top.encode(browserEncScheme) + crlf + body
                    conn.send(response)

    except socket.error as err:
        print("Error connecting to other proxy: " + str(err))
    finally:
        if sOther:
            sOther.close()
        if conn:
            conn.close()


'''
Logic for the server-side proxy
'''
def processServer(conn, client):
    eofFound = False
    bits = bitarray.bitarray()
    while not eofFound:
        # receive request with covert message
        modifiedReq = conn.recv(maxRecvSize).decode(proxyEncScheme)
        if (len(modifiedReq) == 0):
            break

        # extract the covert message
        eofFound = interpretCase(modifiedReq, bits)
        if eofFound:
            extractMessage(bits)

        try:
            # determine intended web server
            webSrv, webPort = determineWebSrv(modifiedReq)
            sWeb = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sWeb.connect((webSrv, webPort))

            # forward request to web server
            sWeb.send(modifiedReq.encode(browserEncScheme))

            # receive the response
            response = sWeb.recv(maxRecvSize)
            headers, crlf, body = response.partition(b'\x0D\x0A\x0D\x0A')
            headers = headers.decode(browserEncScheme)

            if eofFound:
                # get message and convert it to bit representation
                message = input("Enter message to send: ")
                sendBits = bitarray.bitarray()
                sendBits.frombytes(message.encode(proxyEncScheme))

                # use this response to send entire covert message
                messageSent = False
                while not messageSent:
                    # insert covert message, determine if more requests needed
                    modHeaders, messageSent = modifyCase(headers, sendBits)

                    # send modified response to other proxy
                    modResp = modHeaders.encode(proxyEncScheme) + body
                    conn.send(modResp)
            else:
                # send automated blank message to other proxy
                responseLine, headers = extractHeaders(headers)
                responseLine += '  '
                newResponse = responseLine + '\r\n' + headers.as_string()
                modResp = newResponse.encode(proxyEncScheme) + body
                conn.send(modResp)

        except KeyError as err:
            print(str(err))
        except socket.error as err:
            print("Error connecting to web server: " + str(err))

    if sWeb:
        sWeb.close()
    if conn:
        conn.close()


def interpretCase(modifiedReq, bits):
    requestLine, headers = extractHeaders(modifiedReq)
    tuples = headers.items()

    # check for user-entered blank message
    if requestLine.endswith('   '):
        print("Received message:")
        return True
    # check for automated blank message
    elif requestLine.endswith('  '):
        return True

    eofFound = False
    for header, value in tuples:
        chars = list(header)

        for char in chars:
            if char.islower():
                bits.append(False)
            elif char.isupper():
                bits.append(True)

        if value.endswith('  '):
            eofFound = True
            break

    return eofFound


def modifyCase(request, bits):
    # get header-value tuples
    requestLine, headers = extractHeaders(request)
    tuples = headers.items()

    # check for user-entered blank message
    if (bits.length() == 0):
        requestLine += '   '
        newRequest = requestLine + '\r\n' + headers.as_string()
        return newRequest, True

    messageSent = False
    # modify the case of each header
    for i in range(len(tuples)):
        header, value = tuples[i]
        chars = list(header)

        if (bits.length() != 0):
            for j in range(len(chars)):
                if chars[j].isalpha():
                    try:
                        bit = bits.pop()
                    except IndexError:
                        chars[j] = chars[j].lower()
                        continue

                    # bit == 1
                    if bit:
                        chars[j] = chars[j].upper()
                    # bit == 0
                    else:
                        chars[j] = chars[j].lower()

            # append EOF indicator
            if (bits.length() == 0):
                messageSent = True
                value += '  '

        del headers[header]
        newHeader = ''.join(chars)
        headers[newHeader] = value

    # rebuild the request
    newHeaders = headers.as_string()
    newRequest = requestLine + '\r\n' + newHeaders

    return newRequest, messageSent


def determineWebSrv(request):
    requestLine, headers = extractHeaders(request)

    for header, value in headers.items():
        if (header.lower() == 'host'):
            hostAndPort = value.split(':')
            if (len(hostAndPort) == 2):
                return socket.gethostbyname(hostAndPort[0]), hostAndPort[1]
            else:
                return socket.gethostbyname(value), 80

    raise KeyError('Cannot determine intended host')


def extractHeaders(request):
    requestLine, headers = request.split('\r\n', 1)
    headers = email.message_from_string(headers, policy=policy)
    return requestLine, headers


def extractMessage(bits):
    for i in range(bits.length() % 8):
        bits.pop()
    if (bits.length() > 0):
        bits.bytereverse()
        recvMsg = bits.tobytes().decode(proxyEncScheme)[::-1]
        print("Received message: " + recvMsg)


def main():
    global serverMode, otherIP, otherPort

    # check argument length
    if (len(sys.argv) < 5):
        print("Usage: " + sys.argv[0] + " <client/server mode> <port>" + 
            " <other proxy IP> <other proxy port>")
        sys.exit(1)

    # process arguments
    role = sys.argv[1]
    if (role.lower() == "server"):
        serverMode = True
    listPort = int(sys.argv[2])
    otherIP = sys.argv[3]
    otherPort = int(sys.argv[4])

    # open listening socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', listPort))
        s.listen(1)
    except socket.err as err:
        print("Error opening socket: " + err)
        sys.exit(1)

    # handle incoming connections
    while True:
        try:
            conn, client = s.accept()
            if serverMode:
                t = threading.Thread(target=processServer, args=(conn, client))
            else:
                t = threading.Thread(target=processBrowser, args=(conn, client))
            t.start()
        except KeyboardInterrupt:
            if s:
                s.close()
            os._exit(1)


if __name__ == '__main__':
    main()

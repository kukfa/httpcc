# Varying-Case HTTP Covert Channel

By modulating the case of the headers in HTTP requests and responses, we are able to send and receive covert messages over the HTTP protocol.

## Overview
![Overview diagram](http://i.imgur.com/4Z1pByu.png)

The channel follows the request-response model of the HTTP protocol. The two parties that will be communicating covertly are implemented as web proxies: one _browser-facing proxy_ and one _server-facing proxy_. The channel is designed for synchronous communication; the browser-facing proxy sends its entire covert message before the server-facing proxy responds with its own covert message.

The two communicating parties exchange the IP address and port number that their proxy will run on ahead of time. The first party must also set their web browser to forward HTTP requests to the browser-facing proxy.

The channel begins by the first party's web browser forwarding an HTTP request to the browser-facing proxy. The browser-facing proxy will prompt the first party for a covert message to send. It will then modulate the case of each letter in the header field name to encode a hidden binary message within the HTTP request. After encoding the message, the request is sent to the server-facing proxy.

The server-facing proxy will inspect the headers of the HTTP request, and extract the covert message that was encoded by the first party. The request is then sent to the web server originally intended to receive the message, who will return an HTTP response to the server-facing proxy.

The server-facing proxy then prompts the second party for a covert message to send, and will similarly modulate the headers of the HTTP response to encode its message. The response is sent to the browser-facing proxy, who will interpret the case of the headers and extract the covert message. The response is finally forwarded to the web browser, who will load the web page as normal.

## Encoding
To encode binary messages within the HTTP request, the case of the letters in the header field names is modulated. An upper-case letter signifies a bit with a value of 1, and a lower-case letter signifies a bit with a value of 0. Only the case of the header field names are modified; the header field values, start-line, and message body remain intact.

A special indicator is used to signal the end of a covert message to avoid including the remaining headers in the message. To signal the end of a covert message, two trailing whitespaces are appended to the field value of the last header that was modulated. The remaining letters in the header that were not used to encode the message are set to lower-case (0's).

When a proxy decodes a covert message, the stray bits (the remaining bits after extracting as many bytes as possible) are trimmed from the message. However, long header field names with 8 or more leftover bits will bypass this check and are included as part of the message. If these leftover bits are set to 0's, they will be decoded as a null-byte, which will not be visible when printing the covert message as text. However, this still has the potential to add unintended data to the message.

## Long Messages
As we've seen so far, the maximum length of a covert message has been limited by the storage space provided by the header field names in a given HTTP message. At times, either party may wish to send a covert message that exceeds this provided space. Our channel includes two special cases that allow either party to send messages of arbitrary length.

### Browser-Side
When sending a long covert message from the browser-side proxy, the message is sent in chunks using several HTTP requests and reassembled on the server-side proxy.

The browser-side proxy will first send as much of the covert message as it can in a single HTTP request, without using an end-of-message indicator. The server-side proxy will receive the request, forward it to the intended web server, and return the response to the browser-side proxy without sending a covert message of its own. The HTTP response is then forwarded to the web browser, so that the first party can generate additional HTTP requests using the updated web page. These additional requests are used to send the remainder of the covert message.

This process is repeated until the last of the covert message can fit in a given HTTP request, at which point the end-of-message indicator is included as usual. Upon receiving the end-of-message indicator, the server-side proxy then encodes its own covert message into the HTTP response, which is sent to the browser-side proxy to complete the round-trip of the covert channel.

### Server-Side
Similarly, when sending a long covert message from the server-side proxy, the message is sent in chunks using several HTTP responses.

Once the server-side proxy receives the end-of-message indicator from the browser-side proxy and prepares to send its own covert message, it will use the HTTP response it received from the web server to send its entire covert message. This HTTP response is repeatedly modulated and sent to the browser-side proxy until the entire covert message has been sent.

Upon receiving the end-of-message indicator, the browser-side proxy will extract the covert message and forward the last HTTP response it received to the web browser.

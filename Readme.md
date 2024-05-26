# How to run Server

## Single-threaded
```
py Server.py <PORT>
```

## Multi-threaded
```
py Server.py <PORT> -m
```


# Curl Commands to run
## POST

### Text Encoded
```
curl -d '{"key1":"foo", "key2":"bar"}' -H "Content-Type: application/json" http://<host>:<port>/board_name/
```

### Binary Encoded
```
curl --data-binary @<filepath> -H "Content-Type: <mime_type>" -X POST http://<host>:<port>/board_name/
```

## GET

```
curl --get http://<host>:<port>/board_name/<optional entry to get>
```



# Part 2 Analysis
## Running test Script
### Run single Threaded
```
py Server.py <PORT> -t
```

### Run Multi Threaded
```
py Server.py <PORT> -m -t
```

## Test Script details
> An additional optional flag was added to the arguments which is -t to run test script 
> The test script POST numbers from 1 to 100 to a board, and simultaneously GET posted number from board
> The above program is ran 1000 times, and an analysis of results will be posted below

## Test Script Code
```
HOST = ''
PORT = int(sys.argv[1])
MULTI_THREADED= len(sys.argv)==3 and str(sys.argv[2])=='-m'
TEST_PARAM = len (sys.argv)==4 and str(sys.argv[3])=='-t'
TEST_PARAM2 = len (sys.argv) ==3 and str(sys.argv[2])=='-t'



def send_get_request(board_name):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST,PORT))
            request= f"GET /{board_name}/ HTTP/1.1\r\nHOST: {HOST}\r\n\r\n"
            s.sendall(request.encode())
            response = s.recv(4096)
            print(f"GET /{board_name} response: {response.decode()}")
    except Exception as e:
        print(f"GET /{board_name}/ request error: {e}")


def send_post_request(board_name, message):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST,PORT))
            body = f"board={board_name}&message={message}"
            content_length= len(body)
            request= (
                f"POST /{board_name}/ HTTP/1.1\r\n"
                f"HOST: {HOST}:{PORT}\r\n"
                f"Content-Type: application/x-www-form-urlencoded\r\n"
                f"Content-Length: {content_length}\r\n"
                f"\r\n"
                f"{body}"
            )
            s.sendall(request.encode())
            response=s.recv(4096)
            print(f"POST to /{board_name} response: {response.decode()}")
    except Exception as e:
        print(f"POST to /{board_name} request error: {e}")

def send_requests_loop(board_name):
    start=time.time()
    for i in range(1,101):
        message = f"Message {i} on board {board_name}"
        send_post_request(board_name,message)
        send_get_request(board_name)
    end = time.time()
    times_single.append(end-start)

def send_requests_loop_multi(board_name):
    threads = []
    start= time.time()
    for i in range(1,101):
        message=f"Message{i} on board {board_name}"
        thread = threading.Thread(target=send_get_request and send_get_request, args=(board_name,message))
        thread.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    
    end= time.time()
    times_multi.append(end-start)

    

if (TEST_PARAM or TEST_PARAM2):
    board_name="TESTING"
    if(not MULTI_THREADED):
        for i in range(1,1001):
            send_requests_loop(board_name)
        print(f"Running times for single thread {times_single}")
    else:
        for i in range(1,1001):
            send_requests_loop_multi(board_name)
        print(f"Running time for multi threaded {times_multi}")
else:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST,PORT))
        s.listen(socket.SOMAXCONN)

        print(f'Server running on http://{HOST}:{PORT}')

        while True:
            conn,addr =s.accept()
            try:
                if MULTI_THREADED:
                    print("in")
                    t= threading.Thread(target=handle_connection, args=[conn], daemon=True)
                    t.start()
                else:
                    handle_connection(conn)
            except Exception as e:
                print(f"Error: {e}")
                conn.sendall(b'HTTP/1.1 500 Internal Server Error\r\n\r\n')
```

## Analysis results 
![alt text](Analysis.png)

> - From the plots, we can see that the multi-threaded approach is a bit faster than single threaded 
> - Note that both test scripts go under the same evaluation 
> - Something worth noting is due to the large number of requests, the server reaches a point where I connection reset by peer 
> - This is mostly due to Network or connectivity issues 
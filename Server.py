#this file holds the server code 
#plus the database where board messages are stored

import sqlite3
import socket
import pickle
import json
import time
import sys
import threading

times_single=[]
times_multi=[]
# Database code start -------------------------------------
data_conn = sqlite3.connect('messageboard.db',check_same_thread=False)
cursor= data_conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS message_boards (
    name TEXT PRIMARY KEY
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_name TEXT,
    message BLOB,
    FOREIGN KEY(board_name) REFERENCES message_boards(name)
)
''')
#create message board in the table
def insert_message_board(name):
    try:
        cursor.execute('''INSERT INTO message_boards (name) VALUES (?)''', (name,))
        data_conn.commit()
    except:
        print("message board already exists")

#insert message into message board
def insert_message(board_name, message):
    cursor.execute('''SELECT name FROM message_boards WHERE name = ?''', (board_name,))
    board_exists = cursor.fetchone()
    
    if board_exists is None:
        insert_message_board(board_name)
    
    pickled_message = pickle.dumps(message)
    cursor.execute('''INSERT INTO messages (board_name, message) VALUES (?, ?)''',
                   (board_name, pickled_message))
    print(f"Inserted message: {message} into board: {board_name}")
    data_conn.commit()

#retrieve messages from the message board
def get_messages(board_name):
    cursor.execute('''SELECT name FROM message_boards WHERE name= ?''', (board_name,))
    board_exists= cursor.fetchone()

    if board_exists is None:
        print("message cannot be retrieved since board doesn't exist")
        return []
    
    cursor.execute('''SELECT index_num, message FROM messages where board_name= ? ORDER BY index_num''', (board_name,))
    rows = cursor.fetchall()

    messages= [(index_num, pickle.loads(message)) for index_num, message in rows]
    return messages

#End of database code, the database connection is ended when server connection will be closed

#Parsing requests

def parse_request(request):
    try:
        request_line, headers_body = request.split('\r\n', 1)
        method, path, version = request_line.split()
        headers, body= headers_body.split('\r\n\r\n', 1)
        return method, path, version, body
    except ValueError:
        return None, None, None, None

def identify_get_scenario(path):
    parts= path.strip('/').split('/')
    if len(parts) ==0 or parts[0] =='':
        return 'all_boards'
    elif len(parts) == 1:
        return 'board_messages'
    elif len(parts) ==2:
        return 'specific_message'
    else:
        return 'not_found'

def html_get(request_type, parts, cursor):
    print(request_type)
    if request_type == 'all_boards':
        body= '<html><body><h1>Message Boards</h1><ul>'
        cursor.execute("SELECT name FROM message_boards")
        boards=cursor.fetchall()
        for board in boards:
            body+=f'<li><a href="/{board[0]}">{board[0]}</a></li>'
        body += '</ul></body></html>'
    elif request_type =='board_messages':
        board_name = parts[0]
        cursor.execute("SELECT message FROM messages WHERE board_name= ?", (board_name,))
        messages= cursor.fetchall()
        body= f'<html><body><h1>Messages in {board_name}</h1><ul>'
        for message in messages:
            body+=f'<li>{pickle.loads(message[0])}</li>'
        body+= '</ul></body></html>'
    elif request_type == 'specific_message':
        board_name, index=parts
        cursor.execute("SELECT message FROM messages where board_name= ? and id= ?", (board_name,index))
        message= cursor.fetchall()
        if message:
            body=f'<html><body><h1>Message</h1><p>{pickle.loads(message[0][0])}</p></body></html>'
        else:
            body= '<html><body><h1>ERROR: message not found</h1></body></html>'
    else:
        body='<html><body><h1>ERROR: unknow GET request</h1></body></html>'   

    return body


def parse_post(body, content_type):
    if content_type == 'application/json':
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
    elif content_type=='application/x-www-form-urlencoded':
        return parse_urlencoded_data(body)
    else:
        return {}


def parse_urlencoded_data(data):
    def decode_percent_encoded(encoded_str):
        result =''
        i=0
        while i< len(encoded_str):
            if encoded_str == '+':
                result+=' '
            elif encoded_str[i] == '%' and i+2 < len(encoded_str):
                hex_value = encoded_str[i+1:i+3]
                result+=chr(int(hex_value, 16))
                i +=2
            else:
                result += encoded_str[i]
            i += 1
        return result
    
    result = {}
    pairs= data.split('&')
    for pair in pairs:
        if '=' in pair:
            key,value = pair.split('=',1)
            key = decode_percent_encoded(key)
            value = decode_percent_encoded(value)
            result[key] = value
    return result


def handle_post_request(path, body, content_type):
    parts = path.strip('/').split('/')
    print(f"Received Content-Type: {content_type}")
    if len(parts) ==1:
        board_name = parts[0]
        data= parse_post(body,content_type)
        if content_type =='application/json':
            insert_message(board_name,data)
            html_body = f'<html><body><h1>JSON Data Posted to {board_name}</h1><p>{json.dumps(data)}</p></body></html>'
        elif content_type == 'application/x-www-form-urlencoded':
            message = data.get('message', '')
            insert_message(board_name, message)
            html_body= f'<html><body><h1>Message Posted to {board_name}</h1><p>{message}</p></body></html>'
            html_body= html_body.encode('utf-8')
        else:
            html_body = '<html><body><h1>Error Occurred</h1><p>Unsupported Content-Type.</p></body></html>'
    else:
        html_body='<html><body><h1> Error Occured, POST request not processed !</h1></body></html>'
    return html_body

# end of parsing requests code


#server start code



def handle_connection(conn):
    print("Connected by", addr)
    request= conn.recv(2048).decode('UTF-8')
    print("Request:", request)
    method, path, version, body = parse_request(request)
    response_body = ''
    if method == 'GET':
        request_type = identify_get_scenario(path)
        parts=path.strip('/').split('/')
        response_body= html_get(request_type,parts,cursor)
        response = f'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(response_body)}\r\n\r\n{response_body}'
    elif method == 'POST':
        for header in request.split('\r\n'):
            if header.startswith('Content-Type:'):
                content_type = header.split(': ')[1]
                break
        print(f"Received Content-Type: {content_type}")
        response_body = handle_post_request(path,body,content_type)
        response = f'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(response_body)}\r\n\r\n{response_body}'
    else:
        response = 'HTTP/1.1 405 Method Not Allowed\r\n\r\n'
    
    conn.sendall(response.encode('UTF-8'))



#TESTING CODE------ FOR PART 2 ANALYSIS --------
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
        

                
    


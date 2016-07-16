#!/usr/bin/env python3
import sys,socket,itertools,random

def recv_LF(sock):
	r=sock.recv(1024)
	while not 10 in r:
		s=sock.recv(1024)
		if len(s)==0: raise Exception("socket is closed!")
		r+=s
	return r.decode("ascii")[:-1]

def protocol_violation(player_id):
	global num_players
	global conn
	global num_spectators
	global spectators
	print("Protocol violation by player "+str(player_id+1)+"!")
	for i in range(num_players):
		conn[i].sendall("sudden_exit\n".encode("ascii"))
		conn[i].close()
	send_to_spectators("sudden_exit\n".encode("ascii"))
	for i in range(num_spectators): spectators[i].close()
	sys.exit(0)

def valid(x,y): return x>=0 and x<w and y>=0 and y<h

def surrounding(x,y):
	global bombs
	surr=0
	if valid(x-1,y  ): surr+=bombs[w*(y  )+x-1]
	if valid(x-1,y-1): surr+=bombs[w*(y-1)+x-1]
	if valid(x  ,y-1): surr+=bombs[w*(y-1)+x  ]
	if valid(x+1,y-1): surr+=bombs[w*(y-1)+x+1]
	if valid(x+1,y  ): surr+=bombs[w*(y  )+x+1]
	if valid(x+1,y+1): surr+=bombs[w*(y+1)+x+1]
	if valid(x  ,y+1): surr+=bombs[w*(y+1)+x  ]
	if valid(x-1,y+1): surr+=bombs[w*(y+1)+x-1]
	return surr

def board_update(x,y): #return True=bomb, False=just an update of num surrounding values
	global board
	global bombs
	if bombs[w*y+x]: return True
	board[w*y+x]=surrounding(x,y)
	if board[w*y+x]!=0: return False
	if valid(x-1,y  ) and not bombs[w*(y  )+x-1] and board[w*(y  )+x-1]==9: board_update(x-1,y  )
	if valid(x  ,y-1) and not bombs[w*(y-1)+x  ] and board[w*(y-1)+x  ]==9: board_update(x  ,y-1)
	if valid(x+1,y  ) and not bombs[w*(y  )+x+1] and board[w*(y  )+x+1]==9: board_update(x+1,y  )
	if valid(x  ,y+1) and not bombs[w*(y+1)+x  ] and board[w*(y+1)+x  ]==9: board_update(x  ,y+1)
	return False

def send_to_spectators(msg):
	global num_spectators
	global spectators
	defective_spectators=[]
	for i in range(num_spectators):
		try: spectators[i].sendall(msg)
		except Exception: defective_spectators.append(i)
	for i in reversed(defective_spectators):
		try: spectators[i].sendall("sudden_exit\n".encode("ascii"))
		except Exception: pass
		spectators[i].close()
		spectators.pop(i)
		num_spectators-=1

print("Number of players to wait for: ",end="")
num_players=int(input())
print("Width and height: ",end="")
w,h=(int(x) for x in input().split())
print("Number of bombs: ",end="")
num_bombs=int(input())

print("Config: "+str(w)+" "+str(h)+" "+str(num_bombs)+" "+str(num_players))

s=socket.socket()
host=""
port=1337
s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind((host,port))

s.listen(num_players)
conn=[None]*num_players
nickname=[None]*num_players
num_spectators=0
spectators=[]
for i in range(num_players):
	while True:
		conn[i],addr=s.accept()
		print("Connection made.")
		conn[i].sendall(b"multisweeper v1\n")
		try:
			val=recv_LF(conn[i])
		except Exception:
			print("Error in recv.")
			continue
		if val=="multisweeper client v1 ping":
			conn[i].sendall("multisweeper pong\n".encode("ascii"))
			conn[i].close()
			continue
		if val!="multisweeper client v1":
			print("Non-conforming client connected! Not trusted; disconnecting.")
			conn[i].close()
			continue
		print("Conforming client connected.")
		try:
			nickname[i]=recv_LF(conn[i])
		except Exception:
			print("Error in recv.")
			continue
		if nickname[i][:5]!="name ":
			print("Non-conforming client connected - protocol violated. Disconnecting.")
			print(repr(nickname[i]))
			conn[i].close()
			continue
		nickname[i]=nickname[i][5:]
		print("nickname["+str(i)+"]="+nickname[i])
		break

while num_players>1:

	board=[9]*(w*h)
	bombs=[False]*(w*h)
	choices=list(range(w*h))
	for i in range(num_bombs):
		choice=choices[int(random.random()*len(choices))]
		choices.remove(choice)
		bombs[choice]=True

	for i in range(num_players):
		conn[i].sendall(("num_players "+str(num_players)+"\n").encode("ascii"))
		for j in range(num_players):
			conn[i].sendall(("player "+nickname[j]+"\n").encode("ascii"))
	send_to_spectators(("num_players "+str(num_players)+"\n").encode("ascii"))
	for j in range(num_players):
		send_to_spectators(("player "+nickname[j]+"\n").encode("ascii"))

	for i in range(num_players):
		conn[i].sendall(("start "+str(w)+" "+str(h)+" "+str(num_bombs)+"\n").encode("ascii"))
	send_to_spectators(("start "+str(w)+" "+str(h)+" "+str(num_bombs)+"\n").encode("ascii"))

	for turn_id in itertools.count():
		for i in range(num_players):
			conn[i].sendall(("turn_id_update "+str(turn_id+1)+"\n").encode("ascii"))
		send_to_spectators(("turn_id_update "+str(turn_id+1)+"\n").encode("ascii"))
		current_conn=conn[turn_id%num_players]
		current_conn.sendall("turn_start\n".encode("ascii"))
		try:
			response=recv_LF(current_conn)
		except:
			print("Error in recv.")
			protocol_violation(turn_id%num_players)
		if response[:6]!="click ": protocol_violation(turn_id%num_players)
		try: x,y=(int(v) for v in response[6:].split())
		except Exception: protocol_violation(turn_id%num_players)
		if board_update(x,y)==True: #bomb
			board=[10 if bb else bd for (bd,bb) in zip(board,bombs)]
			for i in range(num_players):
				conn[i].sendall(("board_update "+" ".join([str(v) for v in board])+"\n").encode("ascii"))
			send_to_spectators(("board_update "+" ".join([str(v) for v in board])+"\n").encode("ascii"))
			current_conn.sendall("end_condition 0\n".encode("ascii"))
			if num_players==2:
				idx=1-turn_id%num_players
				conn[idx].sendall("end_condition 2\n".encode("ascii"))
				conn[idx].close()
				send_to_spectators("sudden_exit\n".encode("ascii"))
				for spec in spectators: spec.close()
				print("Player "+nickname[idx]+" won the competition!")
				sys.exit(0)
			for i in range(num_players):
				if i!=turn_id%num_players:
					conn[i].sendall("end_condition 1\n".encode("ascii"))
			spectators.append(current_conn)
			num_spectators+=1
			conn.pop(turn_id%num_players)
			nickname.pop(turn_id%num_players)
			num_players-=1
			break
		else:
			for i in range(num_players):
				conn[i].sendall(("board_update "+" ".join([str(v) for v in board])+"\n").encode("ascii"))
			send_to_spectators(("board_update "+" ".join([str(v) for v in board])+"\n").encode("ascii"))
























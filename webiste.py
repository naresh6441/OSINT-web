from flask import Flask, request, jsonify, session, render_template_string, send_file, Response
import sqlite3
import secrets
import io
import os
from functools import wraps
from datetime import datetime

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "osint.db")

app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

PAYMENT_AMOUNT = 100
UPI_ID = "your-upi@bank"

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

MAX_QR_SIZE = 2 * 1024 * 1024

STATUSES = [
    "Payment Pending",
    "Payment Submitted",
    "Payment Verified",
    "Information Ready"
]


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE NOT NULL,
            numbers TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Payment Pending',
            payment_submitted INTEGER DEFAULT 0,
            payment_verified INTEGER DEFAULT 0,
            name TEXT DEFAULT '',
            location TEXT DEFAULT '',
            details TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value BLOB,
            mimetype TEXT
        )
    """)

    conn.commit()
    conn.close()


def make_request_id():
    return "OSINT-" + secrets.token_hex(6).upper()


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({
                "success": False,
                "message": "Admin login required."
            }), 401
        return func(*args, **kwargs)
    return wrapper


HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OSINT LOOKUP</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{
font-family:Arial,sans-serif;
background:radial-gradient(circle at top left,#092c3b,transparent 35%),
radial-gradient(circle at bottom right,#24103c,transparent 35%),#050812;
color:#fff;min-height:100vh
}
body:before{
content:"";position:fixed;inset:0;pointer-events:none;
background-image:linear-gradient(rgba(0,255,200,.035) 1px,transparent 1px),
linear-gradient(90deg,rgba(0,255,200,.035) 1px,transparent 1px);
background-size:35px 35px
}
.container{max-width:650px;margin:auto;padding:15px}
.header{text-align:center;padding:20px 5px}
.logo{
width:70px;height:70px;margin:auto;border-radius:20px;
display:flex;align-items:center;justify-content:center;
font-size:28px;font-weight:900;color:#02050a;
background:linear-gradient(135deg,#00ffd5,#00a8ff,#9b4dff);
box-shadow:0 0 25px rgba(0,255,213,.3)
}
.title{
margin-top:14px;font-size:29px;font-weight:900;letter-spacing:2px;
background:linear-gradient(90deg,#00ffd5,#00a8ff,#c66cff);
-webkit-background-clip:text;color:transparent
}
.subtitle{margin-top:6px;color:#8fa7b7;font-size:13px}
.tabs{display:flex;gap:8px;margin-bottom:15px}
.tab{
flex:1;text-align:center;padding:11px;border-radius:12px;
background:#0a1420;border:1px solid #1c3443;color:#8298a5
}
.tab.active{color:#00ffd5;border-color:#00ffd5;background:rgba(0,255,213,.06)}
.card{
background:rgba(9,16,29,.85);border:1px solid rgba(0,255,213,.16);
border-radius:20px;padding:18px;margin-bottom:15px;
box-shadow:0 15px 50px rgba(0,0,0,.25);backdrop-filter:blur(15px)
}
.card h2{font-size:18px;margin-bottom:14px}
.label{display:block;color:#8fa7b7;font-size:12px;margin-bottom:6px}
.field{margin-bottom:13px}
input,textarea,select{
width:100%;padding:13px;border-radius:12px;background:#080e18;
border:1px solid #1c3443;color:white;outline:none;font-size:14px
}
input:focus,textarea:focus,select:focus{border-color:#00ffd5}
textarea{min-height:90px;resize:vertical}
.row{display:flex;gap:9px}
.row>*{flex:1}
button{
border:0;border-radius:12px;padding:13px 16px;font-weight:800;
cursor:pointer;color:#031016;background:linear-gradient(135deg,#00ffd5,#00a8ff)
}
button:disabled{opacity:.5;cursor:not-allowed}
.full{width:100%}
.secondary{background:#111d2b;color:#b8d2df;border:1px solid #203848}
.purple{background:linear-gradient(135deg,#b44cff,#5c5cff);color:#fff}
.danger{background:linear-gradient(135deg,#ff4567,#ff783f);color:#fff}
.number-item{
display:flex;justify-content:space-between;align-items:center;
padding:10px 12px;margin:7px 0;border-radius:11px;
background:#0b1522;border:1px solid #193444;font-family:monospace
}
.remove{background:transparent;color:#ff6580;padding:3px 7px}
.status{
display:inline-block;padding:7px 12px;border-radius:30px;
color:#00ffd5;background:rgba(0,255,213,.08);
border:1px solid rgba(0,255,213,.25);font-size:12px;font-weight:bold
}
.pending{color:#ffc857;border-color:rgba(255,200,87,.3);background:rgba(255,200,87,.08)}
.ready{color:#6dff91;border-color:rgba(109,255,145,.3);background:rgba(109,255,145,.08)}
.qr{background:#fff;padding:12px;border-radius:17px;width:250px;max-width:100%;margin:15px auto}
.qr img{width:100%;display:block;border-radius:7px}
.upi{text-align:center;color:#94aab8;font-size:13px;margin:10px}
.request-id{
font-family:monospace;color:#00ffd5;background:#06151b;
border:1px solid #163e47;padding:10px;border-radius:10px;
text-align:center;word-break:break-all;margin:10px 0
}
.info{
padding:13px;border-radius:12px;background:#09131f;
border:1px solid #183344;margin-bottom:9px
}
.info small{display:block;color:#718896;margin-bottom:5px}
.info strong{word-break:break-word}
.notice{
padding:12px;border-radius:12px;background:rgba(255,193,7,.06);
border:1px solid rgba(255,193,7,.2);color:#d6c58b;font-size:12px;line-height:1.6
}
.success{
padding:13px;border-radius:12px;background:rgba(71,255,135,.07);
border:1px solid rgba(71,255,135,.22);color:#8affad
}
.error{
padding:13px;border-radius:12px;background:rgba(255,60,90,.07);
border:1px solid rgba(255,60,90,.2);color:#ff8799
}
.admin-request{
border:1px solid #1b3443;background:#08121e;border-radius:16px;
padding:14px;margin-bottom:12px
}
.admin-top{display:flex;justify-content:space-between;gap:8px;align-items:center}
.admin-id{color:#00ffd5;font-family:monospace;font-size:12px;word-break:break-all}
.admin-numbers{color:#c8d7de;font-family:monospace;font-size:13px;margin:10px 0}
.hidden{display:none!important}
hr{border:0;border-top:1px solid #17303d;margin:15px 0}
.footer{text-align:center;color:#526773;font-size:11px;line-height:1.7;padding:20px}
@media(max-width:500px){.container{padding:10px}.row{flex-direction:column}.title{font-size:25px}.card{padding:15px}}
</style>
</head>
<body>
<div class="container">

<div class="header">
<div class="logo">OS</div>
<div class="title">OSINT LOOKUP</div>
<div class="subtitle">Secure Manual Information Request System</div>
</div>

<div class="tabs">
<div id="ctab" class="tab active" onclick="panel('customer')">CUSTOMER</div>
<div id="atab" class="tab" onclick="panel('admin')">ADMIN</div>
</div>

<div id="customer">

<div class="card">
<h2>📱 Create Lookup Request</h2>
<div class="field">
<label class="label">Enter Number</label>
<div class="row">
<input id="num" inputmode="numeric" placeholder="Enter number">
<button onclick="addNumber()">+ Add</button>
</div>
</div>
<div id="numbers"></div>
</div>

<div id="payCard" class="card hidden">
<h2>💳 Payment</h2>
<div class="notice">
Payment verification is performed manually by the administrator.
</div>
<div class="qr">
<img id="customerQR" src="/payment-qr" alt="Payment QR">
</div>
<div class="upi">
UPI: <b>{{ upi_id }}</b><br>
Amount: <b>₹{{ payment_amount }}</b>
</div>
<button id="payBtn" class="full" onclick="pay()">✅ I HAVE COMPLETED PAYMENT</button>
</div>

<div id="statusCard" class="card hidden">
<h2>📊 Request Status</h2>
<div class="request-id" id="rid"></div>
<div id="status" style="text-align:center;margin:12px"></div>
<button class="secondary full" onclick="refresh()">🔄 Refresh Status</button>
</div>

<div id="result" class="card hidden">
<h2>🔐 Information</h2>
<div class="success">Information has been manually published by the administrator.</div>
<br>
<div id="resultNumbers"></div>
<div class="info"><small>Name</small><strong id="rname">—</strong></div>
<div class="info"><small>Location</small><strong id="rlocation">—</strong></div>
<div class="info"><small>Additional Details</small><strong id="rdetails">—</strong></div>
<div class="info"><small>Notes</small><strong id="rnotes">—</strong></div>
</div>

<div class="card">
<h2>🔎 Check Existing Request</h2>
<div class="field">
<input id="searchId" placeholder="Enter Request ID">
</div>
<button class="purple full" onclick="findRequest()">Search Request</button>
</div>

</div>

<div id="admin" class="hidden">

<div id="loginCard" class="card">
<h2>🔐 Admin Login</h2>
<div class="field">
<label class="label">Username</label>
<input id="user" value="admin">
</div>
<div class="field">
<label class="label">Password</label>
<input id="pass" type="password" placeholder="Password">
</div>
<button class="full" onclick="login()">LOGIN</button>
<div id="loginMsg"></div>
</div>

<div id="dashboard" class="hidden">

<div class="card">
<div class="admin-top">
<h2>🛡️ Admin Dashboard</h2>
<button class="danger" onclick="logout()">Logout</button>
</div>
<div class="subtitle">Manual payment and information management</div>
</div>

<div class="card">
<h2>💳 Payment QR</h2>
<div class="notice">Upload your own PNG/JPG/WEBP payment QR.</div>
<br>
<input id="qrfile" type="file" accept="image/png,image/jpeg,image/webp">
<br><br>
<button onclick="uploadQR()">Upload QR</button>
<div class="qr"><img id="adminQR" src="/payment-qr"></div>
</div>

<div class="card">
<div class="admin-top">
<h2>📋 Requests</h2>
<button class="secondary" onclick="loadRequests()">🔄 Refresh</button>
</div>
<div id="requests"></div>
</div>

</div>
</div>

<div class="footer">
OSINT LOOKUP SYSTEM<br>
Manual information delivery only.<br>
Use only for lawful and authorized purposes.
</div>
</div>

<script>
let nums=[];
let requestId=null;
let timer=null;

function esc(v){
return String(v??"").replace(/&/g,"&amp;").replace(/</g,"&lt;")
.replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");
}

function panel(p){
document.getElementById("customer").classList.toggle("hidden",p!=="customer");
document.getElementById("admin").classList.toggle("hidden",p!=="admin");
document.getElementById("ctab").classList.toggle("active",p==="customer");
document.getElementById("atab").classList.toggle("active",p==="admin");
}

function renderNumbers(){
let box=document.getElementById("numbers");
box.innerHTML="";
nums.forEach((n,i)=>{
box.innerHTML+=`<div class="number-item"><span>${esc(n)}</span>
<button class="remove" onclick="removeNum(${i})">✕</button></div>`;
});
}

function removeNum(i){
if(requestId){
alert("Request already created. Start a new request for different numbers.");
return;
}
nums.splice(i,1);
renderNumbers();
}

async function addNumber(){
let input=document.getElementById("num");
let n=input.value.replace(/[^0-9+]/g,"").trim();

if(!n || n.length<5){
alert("Enter a valid number.");
return;
}
if(nums.includes(n)){
alert("Number already added.");
return;
}

nums.push(n);
input.value="";
renderNumbers();

if(!requestId){
let r=await fetch("/api/request",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({numbers:nums})
});
let d=await r.json();

if(!d.success){
nums.pop();
renderNumbers();
alert(d.message);
return;
}

requestId=d.request_id;
history.replaceState(null,"","?request="+encodeURIComponent(requestId));

document.getElementById("payCard").classList.remove("hidden");
document.getElementById("statusCard").classList.remove("hidden");
document.getElementById("rid").textContent=requestId;
startPolling();
}
}

async function pay(){
if(!requestId)return;

let b=document.getElementById("payBtn");
b.disabled=true;
b.textContent="Submitting...";

let r=await fetch("/api/request/"+encodeURIComponent(requestId)+"/payment",{method:"POST"});
let d=await r.json();

if(!d.success){
alert(d.message);
b.disabled=false;
b.textContent="✅ I HAVE COMPLETED PAYMENT";
return;
}

b.textContent="✅ PAYMENT SUBMITTED";
refresh();
}

async function loadRequest(id,silent=false){
if(!id)return;

try{
let r=await fetch("/api/request/"+encodeURIComponent(id));
let d=await r.json();

if(!d.success){
if(!silent)alert(d.message);
return;
}

requestId=d.request.request_id;
document.getElementById("statusCard").classList.remove("hidden");
document.getElementById("rid").textContent=requestId;

let cls="";
if(d.request.status==="Payment Pending")cls="pending";
if(d.request.status==="Information Ready")cls="ready";

document.getElementById("status").innerHTML=
`<span class="status ${cls}">${esc(d.request.status)}</span>`;

if(d.request.payment_submitted){
document.getElementById("payCard").classList.remove("hidden");
document.getElementById("payBtn").disabled=true;
document.getElementById("payBtn").textContent="✅ PAYMENT SUBMITTED";
}

if(d.request.status==="Information Ready"){
showResult(d.request);
stopPolling();
}else{
startPolling();
}
}catch(e){
if(!silent)alert("Server connection failed.");
}
}

function refresh(){
if(requestId)loadRequest(requestId);
}

function startPolling(){
stopPolling();
timer=setInterval(()=>{if(requestId)loadRequest(requestId,true)},5000);
}

function stopPolling(){
if(timer){clearInterval(timer);timer=null;}
}

function showResult(d){
document.getElementById("result").classList.remove("hidden");

let b=document.getElementById("resultNumbers");
b.innerHTML="";
d.numbers.forEach(n=>{
b.innerHTML+=`<div class="info"><small>Number</small><strong>${esc(n)}</strong></div>`;
});

document.getElementById("rname").textContent=d.name||"Not provided";
document.getElementById("rlocation").textContent=d.location||"Not provided";
document.getElementById("rdetails").textContent=d.details||"Not provided";
document.getElementById("rnotes").textContent=d.notes||"Not provided";
}

function findRequest(){
let id=document.getElementById("searchId").value.trim();
if(!id){alert("Enter Request ID.");return;}
requestId=id;
history.replaceState(null,"","?request="+encodeURIComponent(id));
loadRequest(id);
}

async function login(){
let r=await fetch("/api/admin/login",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({
username:document.getElementById("user").value,
password:document.getElementById("pass").value
})
});
let d=await r.json();

if(!d.success){
document.getElementById("loginMsg").innerHTML=`<div class="error">${esc(d.message)}</div>`;
return;
}

document.getElementById("loginCard").classList.add("hidden");
document.getElementById("dashboard").classList.remove("hidden");
loadRequests();
}

async function logout(){
await fetch("/api/admin/logout",{method:"POST"});
location.reload();
}

async function loadRequests(){
let box=document.getElementById("requests");
box.innerHTML="Loading...";

let r=await fetch("/api/admin/requests");
if(r.status===401){
location.reload();
return;
}

let d=await r.json();

if(!d.requests.length){
box.innerHTML='<div class="notice">No requests yet.</div>';
return;
}

box.innerHTML="";

d.requests.forEach(x=>{
let safeId=esc(x.request_id);

let div=document.createElement("div");
div.className="admin-request";

div.innerHTML=`
<div class="admin-top">
<div class="admin-id">${safeId}</div>
<span class="status">${esc(x.status)}</span>
</div>

<div class="admin-numbers">${esc(x.numbers)}</div>
<div class="subtitle">Created: ${esc(x.created_at)}</div>
<hr>

<div class="field">
<label class="label">Status</label>
<select id="st_${safeId}">
<option ${x.status==="Payment Pending"?"selected":""}>Payment Pending</option>
<option ${x.status==="Payment Submitted"?"selected":""}>Payment Submitted</option>
<option ${x.status==="Payment Verified"?"selected":""}>Payment Verified</option>
<option ${x.status==="Information Ready"?"selected":""}>Information Ready</option>
</select>
</div>

<button class="secondary full" onclick="updateStatus('${safeId}')">Update Status</button>
<br><br>
<button class="full" onclick="verify('${safeId}')">💰 Verify Payment</button>

<br><br>

<div class="field">
<label class="label">Name</label>
<input id="name_${safeId}" value="${esc(x.name)}" placeholder="Enter name">
</div>

<div class="field">
<label class="label">Location</label>
<input id="loc_${safeId}" value="${esc(x.location)}" placeholder="Enter location">
</div>

<div class="field">
<label class="label">Additional Details</label>
<textarea id="det_${safeId}" placeholder="Enter manually verified information">${esc(x.details)}</textarea>
</div>

<div class="field">
<label class="label">Notes</label>
<textarea id="notes_${safeId}" placeholder="Enter notes">${esc(x.notes)}</textarea>
</div>

<button class="purple full" onclick="publish('${safeId}')">🚀 Publish Information</button>
<br><br>
<button class="danger full" onclick="delRequest('${safeId}')">🗑 Delete Request</button>
`;

box.appendChild(div);
});
}

async function verify(id){
if(!confirm("Confirm manually received and verified payment?"))return;

let r=await fetch("/api/admin/request/"+encodeURIComponent(id)+"/verify",{method:"POST"});
let d=await r.json();

if(!d.success){alert(d.message);return;}
alert("Payment verified.");
loadRequests();
}

async function updateStatus(id){
let status=document.getElementById("st_"+id).value;

let r=await fetch("/api/admin/request/"+encodeURIComponent(id)+"/status",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({status:status})
});
let d=await r.json();

if(!d.success){alert(d.message);return;}
loadRequests();
}

async function publish(id){
let name=document.getElementById("name_"+id).value;
let location=document.getElementById("loc_"+id).value;
let details=document.getElementById("det_"+id).value;
let notes=document.getElementById("notes_"+id).value;

let r=await fetch("/api/admin/request/"+encodeURIComponent(id)+"/information",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({name,location,details,notes})
});
let d=await r.json();

if(!d.success){alert(d.message);return;}
alert("Information published.");
loadRequests();
}

async function delRequest(id){
if(!confirm("Delete this request permanently?"))return;

let r=await fetch("/api/admin/request/"+encodeURIComponent(id),{method:"DELETE"});
let d=await r.json();

if(!d.success){alert(d.message);return;}
loadRequests();
}

async function uploadQR(){
let file=document.getElementById("qrfile").files[0];

if(!file){
alert("Select QR image.");
return;
}

if(file.size>2097152){
alert("QR image must be below 2 MB.");
return;
}

let form=new FormData();
form.append("qr",file);

let r=await fetch("/api/admin/qr",{method:"POST",body:form});
let d=await r.json();

if(!d.success){alert(d.message);return;}

alert("QR uploaded.");
document.getElementById("adminQR").src="/payment-qr?t="+Date.now();
document.getElementById("customerQR").src="/payment-qr?t="+Date.now();
}

window.addEventListener("DOMContentLoaded",()=>{
let id=new URLSearchParams(location.search).get("request");
if(id){
requestId=id;
loadRequest(id);
}
});
</script>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(
        HTML,
        payment_amount=PAYMENT_AMOUNT,
        upi_id=UPI_ID
    )


@app.route("/api/request", methods=["POST"])
def create_request():
    data = request.get_json(silent=True) or {}
    numbers = data.get("numbers", [])

    if not isinstance(numbers, list):
        return jsonify({"success": False, "message": "Invalid numbers."}), 400

    cleaned = []
    for n in numbers:
        n = str(n).strip()
        if len(n) >= 5:
            cleaned.append(n)

    cleaned = list(dict.fromkeys(cleaned))

    if not cleaned:
        return jsonify({
            "success": False,
            "message": "Please add at least one valid number."
        }), 400

    rid = make_request_id()
    t = now()

    conn = db()
    conn.execute("""
        INSERT INTO requests
        (request_id,numbers,status,created_at,updated_at)
        VALUES (?,?,?,?,?)
    """, (
        rid,
        "\n".join(cleaned),
        "Payment Pending",
        t,
        t
    ))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "request_id": rid})


@app.route("/api/request/<request_id>")
def get_request(request_id):
    conn = db()
    row = conn.execute(
        "SELECT * FROM requests WHERE request_id=?",
        (request_id,)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({
            "success": False,
            "message": "Request not found."
        }), 404

    numbers = [x for x in row["numbers"].split("\n") if x]

    return jsonify({
        "success": True,
        "request": {
            "request_id": row["request_id"],
            "numbers": numbers,
            "status": row["status"],
            "payment_submitted": bool(row["payment_submitted"]),
            "payment_verified": bool(row["payment_verified"]),
            "name": row["name"],
            "location": row["location"],
            "details": row["details"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    })


@app.route("/api/request/<request_id>/payment", methods=["POST"])
def payment(request_id):
    conn = db()
    row = conn.execute(
        "SELECT * FROM requests WHERE request_id=?",
        (request_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Request not found."
        }), 404

    conn.execute("""
        UPDATE requests
        SET payment_submitted=1,
            status='Payment Submitted',
            updated_at=?
        WHERE request_id=?
    """, (now(), request_id))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Payment submitted for manual verification."
    })


@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}

    if (
        str(data.get("username", "")).strip() == ADMIN_USERNAME
        and str(data.get("password", "")) == ADMIN_PASSWORD
    ):
        session["admin_logged_in"] = True
        return jsonify({"success": True})

    return jsonify({
        "success": False,
        "message": "Invalid username or password."
    }), 401


@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/admin/requests")
@admin_required
def admin_requests():
    conn = db()
    rows = conn.execute(
        "SELECT * FROM requests ORDER BY id DESC"
    ).fetchall()
    conn.close()

    result = []

    for row in rows:
        result.append({
            "request_id": row["request_id"],
            "numbers": row["numbers"],
            "status": row["status"],
            "payment_submitted": bool(row["payment_submitted"]),
            "payment_verified": bool(row["payment_verified"]),
            "name": row["name"],
            "location": row["location"],
            "details": row["details"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })

    return jsonify({
        "success": True,
        "requests": result
    })


@app.route("/api/admin/request/<request_id>/verify", methods=["POST"])
@admin_required
def verify(request_id):
    conn = db()

    row = conn.execute(
        "SELECT * FROM requests WHERE request_id=?",
        (request_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Request not found."
        }), 404

    if not row["payment_submitted"]:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Customer has not submitted payment."
        }), 400

    conn.execute("""
        UPDATE requests
        SET payment_verified=1,
            status='Payment Verified',
            updated_at=?
        WHERE request_id=?
    """, (now(), request_id))

    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route("/api/admin/request/<request_id>/status", methods=["POST"])
@admin_required
def update_status(request_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).strip()

    if status not in STATUSES:
        return jsonify({
            "success": False,
            "message": "Invalid status."
        }), 400

    conn = db()

    row = conn.execute(
        "SELECT * FROM requests WHERE request_id=?",
        (request_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Request not found."
        }), 404

    if status == "Payment Verified" and not row["payment_submitted"]:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Payment must be submitted first."
        }), 400

    if status == "Information Ready" and not row["payment_verified"]:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Verify payment first."
        }), 400

    conn.execute("""
        UPDATE requests
        SET status=?, updated_at=?
        WHERE request_id=?
    """, (status, now(), request_id))

    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route(
    "/api/admin/request/<request_id>/information",
    methods=["POST"]
)
@admin_required
def publish_information(request_id):
    data = request.get_json(silent=True) or {}

    conn = db()

    row = conn.execute(
        "SELECT * FROM requests WHERE request_id=?",
        (request_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Request not found."
        }), 404

    if not row["payment_verified"]:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Verify payment first."
        }), 400

    conn.execute("""
        UPDATE requests
        SET name=?,
            location=?,
            details=?,
            notes=?,
            status='Information Ready',
            updated_at=?
        WHERE request_id=?
    """, (
        str(data.get("name", "")).strip(),
        str(data.get("location", "")).strip(),
        str(data.get("details", "")).strip(),
        str(data.get("notes", "")).strip(),
        now(),
        request_id
    ))

    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route("/api/admin/request/<request_id>", methods=["DELETE"])
@admin_required
def delete_request(request_id):
    conn = db()
    cur = conn.execute(
        "DELETE FROM requests WHERE request_id=?",
        (request_id,)
    )
    conn.commit()
    conn.close()

    if cur.rowcount == 0:
        return jsonify({
            "success": False,
            "message": "Request not found."
        }), 404

    return jsonify({"success": True})


@app.route("/payment-qr")
def payment_qr():
    conn = db()
    row = conn.execute("""
        SELECT value,mimetype
        FROM settings
        WHERE key='payment_qr'
    """).fetchone()
    conn.close()

    if row and row["value"]:
        return send_file(
            io.BytesIO(row["value"]),
            mimetype=row["mimetype"]
        )

    svg = """<svg xmlns="http://www.w3.org/2000/svg"
    width="500" height="500">
    <rect width="500" height="500" fill="white"/>
    <rect x="30" y="30" width="440" height="440"
    fill="#eee" stroke="#111" stroke-width="5"/>
    <text x="250" y="230" text-anchor="middle"
    font-family="Arial" font-size="28">PAYMENT QR</text>
    <text x="250" y="275" text-anchor="middle"
    font-family="Arial" font-size="18">Upload QR from Admin</text>
    </svg>"""

    return Response(svg, mimetype="image/svg+xml")


@app.route("/api/admin/qr", methods=["POST"])
@admin_required
def upload_qr():
    file = request.files.get("qr")

    if not file:
        return jsonify({
            "success": False,
            "message": "No QR image selected."
        }), 400

    if not file.mimetype.startswith("image/"):
        return jsonify({
            "success": False,
            "message": "Please upload an image."
        }), 400

    data = file.read()

    if len(data) > MAX_QR_SIZE:
        return jsonify({
            "success": False,
            "message": "QR image must be below 2 MB."
        }), 400

    conn = db()
    conn.execute("""
        INSERT OR REPLACE INTO settings
        (key,value,mimetype)
        VALUES ('payment_qr',?,?)
    """, (sqlite3.Binary(data), file.mimetype))

    conn.commit()
    conn.close()

    return jsonify({"success": True})


if __name__ == "__main__":
    init_db()

    print("=" * 45)
    print("        OSINT LOOKUP SERVER")
    print("=" * 45)
    print("Admin Username :", ADMIN_USERNAME)
    print("Payment Amount :", PAYMENT_AMOUNT)
    print("UPI ID         :", UPI_ID)
    print("Open           : http://127.0.0.1:5000")
    print("=" * 45)

    app.run(host="0.0.0.0", port=5000, debug=False)


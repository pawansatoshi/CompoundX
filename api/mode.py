from http.server import BaseHTTPRequestHandler

from compoundx.vercel_http import send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        send_json(self, {"mode": "PAPER", "live_orders": False, "withdrawals": False})

import requests


def lambda_handler(event, context):
    ip = requests.get("https://ifconfig.co/json").json()["ip"]
    return {"msg": f"Hello, World! I'm taking to you from {ip}"}

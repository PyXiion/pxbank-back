import asyncio
from dotenv import load_dotenv


load_dotenv(dotenv_path='.env')

import api.auth, api.transactions, api.currencies, api.accounts, api.push
from pxws.server import Server


server = Server()

server.add_route(api.auth.route)
server.add_route(api.transactions.route)
server.add_route(api.currencies.route)
server.add_route(api.accounts.route)
server.add_route(api.push.route)

asyncio.run(server.serve_forever('localhost', 4000))

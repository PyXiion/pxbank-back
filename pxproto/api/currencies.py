import proto_models
from pxws.route import Route

route = Route()

@route.on('currencies/fetch')
async def fetch_transactions() -> list:
  return [

  ]
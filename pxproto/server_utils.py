from pxws.server import Server


async def get_connection_to_user(server: Server, user_id: int):
  for connection in server.connections_it:
    if connection.get_metadata('user_id') == user_id:

      return connection

  return None
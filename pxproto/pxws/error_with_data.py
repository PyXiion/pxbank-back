class ProtocolError(Exception):
  def __init__(self, message: str):
    self.message = message

class ErrorWithData(ProtocolError):
  def __init__(self, message: str, data: any = None):
    ProtocolError.__init__(self, message)
    self.data = data

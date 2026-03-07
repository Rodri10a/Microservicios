
import os # lee variables de entorno 
# verificar tokens JWT.
SECRET_KEY     = os.getenv("SECRET_KEY", "RorroArguello") 
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "token_interno")

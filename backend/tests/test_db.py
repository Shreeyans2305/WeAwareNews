import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from google.cloud.sql.connector import Connector, IPTypes
from google.cloud import secretmanager

client = secretmanager.SecretManagerServiceClient()
name = "projects/project-9ba21d45-1dfd-4108-b69/secrets/db-password/versions/latest"
pw = client.access_secret_version(request={"name": name}).payload.data.decode("UTF-8").strip()

connector = Connector()
conn = connector.connect(
    "project-9ba21d45-1dfd-4108-b69:us-central1:weaware-pg",
    "pg8000",
    user="weaware_user",
    password=pw,
    db="weaware",
    ip_type=IPTypes.PUBLIC,
)
cur = conn.cursor()
cur.execute("SELECT 1")
print("SUCCESS:", cur.fetchone())
cur.close()
conn.close()
connector.close()

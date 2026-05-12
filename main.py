from fastapi import FastAPI
from sqlmodel import create_engine
from sqlmodel import SQLModel

#Partie 1 : 

sqlite_file_name = "messagerie.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=False) # echo=False pour garder la console propre

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# Lifespan : Initialise la BDD au démarrage de l'API
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan, title="API de Messagerie")

# Dépendance pour obtenir une session BDD
def get_session():
    with Session(engine) as session:
        yield session
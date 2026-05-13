from fastapi import FastAPI
from sqlmodel import create_engine
from sqlmodel import SQLModel

#Partie 1 : Mise en place du projet

#Je configure la base de données SQL d'abord
nom_fichier= "messagerie.db"
url= f"sqlite:///{nom_fichier}"
console =create_engine(url, echo=False) #echo=False pour garder la console propre

#Création de tables sql
def create_db_and_tables():
    SQLModel.metadata.create_all(console)

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
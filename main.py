'''
Pablo Thoumyre--Rivero Campoy
TP Messagerie

Ce travail se compose de deux parties : 
- Le code (divisé en 5 parties comme expliquées dans le fichier Readme)
- Les réponses aux questions demandées dans le travail d'analyse '''





#Import des bibliothèques
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import EmailStr
from sqlmodel import Field, Session, SQLModel, create_engine, select







#Partie 1 : Mise en place du projet Asynchrone
'''Je fonctionne en asynchrone comme vu en cours 
pour éviter que la base de données ne se crée qu'après que l'API se soit lancée'''

#Je configure la base de données SQL d'abord
nom_fichier= "messagerie.db"
url= f"sqlite:///{nom_fichier}"
console =create_engine(url, echo=False) #echo=False pour garder la console propre

#Initialisation
@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(console)
    yield
app = FastAPI(lifespan=lifespan, title="Application de Messagerie")

# Dépendance pour obtenir une session BDD
def get_session():
    with Session(console) as session:
        yield session









#Partie 2 : Définition des schémas
'''On veut bien tout séparer et ne pas afficher toute la base
On veut poser des conditions donc utilise le module Field de SQL'''

#Utilisateur
class UserBase(SQLModel):
    username: str = Field(index=True, unique=True) #unique=True évite les doublons
    email: EmailStr # Pydantic valide l'email

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    #l'id est optionnel parce qu'avant de créer son comtpe, l'utilisateur n'a pas d'id

class UserCreate(UserBase):
    pass

class UserRead(UserBase):
    id: int #obligatoire cette fois

#Messages (même logique que pour les utilisateurs mais avec quelques règles et quelques champs en plus)
class MessageBase(SQLModel):
    subject: str = Field(min_length=1) #Empêche les sujets vides
    body: str = Field(min_length=1)    #Empêche les messages vides

class Message(MessageBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sender_id: int = Field(foreign_key="user.id")
    receiver_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_read: bool = Field(default=False)

class MessageCreate(MessageBase):
    sender_id: int
    receiver_id: int

class MessageRead(MessageBase):
    id: int
    sender_id: int
    receiver_id: int
    created_at: datetime
    is_read: bool











#Partie 3 : API Utilisateurs

#Creation d'un utilisateur et on regarde s'il existe déjà
@app.post("/users", response_model=UserRead, status_code=201)
def create_user(user: UserCreate, session: Session = Depends(get_session)):
    # Vérification de l'unicité du nom d'utilisateur
    existing_user = session.exec(select(User).where(User.username == user.username)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Ce nom d'utilisateur existe déjà.")
    db_user = User.model_validate(user)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

#On peut rechercher la liste des utilisateurs
@app.get("/users", response_model=List[UserRead])
def read_users(session: Session = Depends(get_session)):
    return session.exec(select(User)).all()

#On peut rechercher un seul utilisateur et on renvoie une erreur s'il n'existe pas
@app.get("/users/{user_id}", response_model=UserRead)
def read_user(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
    return user










#Partie 4 : API messages

#Envoyer un message
@app.post("/messages", response_model=MessageRead, status_code=201)
def create_message(message: MessageCreate, session: Session = Depends(get_session)):
    #Pas de message à soi-même
    if message.sender_id == message.receiver_id: 
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous envoyer un message à vous-même.")
    
    #Expéditeur et destinataire existent
    sender = session.get(User, message.sender_id)
    receiver = session.get(User, message.receiver_id)
    if not sender or not receiver: 
        raise HTTPException(status_code=404, detail="Expéditeur ou destinataire introuvable.")
    
    #Création message et sauvegarde
    db_message = Message.model_validate(message)
    session.add(db_message)
    session.commit()
    session.refresh(db_message)
    return db_message

#Suite Partie 4 et ajout de la partie 5 filtres : J'ai choisi le 1er (messages non-lus) et le 2eme (sur la pagination)
@app.get("/users/{user_id}/inbox", response_model=List[MessageRead])
def read_inbox(
    user_id: int, 
    session: Session = Depends(get_session),
    unread_only: bool = False, #messages non lus
    limit: int = Query(default=20, le=100), #pagination améliorée
    offset: int=0
):
    user= session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
    query = select(Message).where(Message.receiver_id == user_id) #syntaxe sql
    
    if unread_only: #Filtrage selon les messages non lus
        query = query.where(Message.is_read == False)
        
    query = query.order_by(Message.created_at.desc()).offset(offset).limit(limit)
    return session.exec(query).all()

#voir les messages envoyés par un utilisateur
@app.get("/users/{user_id}/sent", response_model=List[MessageRead])
def read_sent_messages(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
    
    query = select(Message).where(Message.sender_id == user_id).order_by(Message.created_at.desc())
    return session.exec(query).all()

#voir le détail d'un message
@app.get("/messages/{message_id}", response_model=MessageRead)
def read_message(message_id: int, session: Session = Depends(get_session)):
    message = session.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message non trouvé.")
    return message

#marquer un message comme lu
@app.patch("/messages/{message_id}/read", response_model=MessageRead)
def mark_message_as_read(message_id: int, session: Session = Depends(get_session)):
    message = session.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message non trouvé.")
    
    message.is_read = True
    session.add(message)
    session.commit()
    session.refresh(message)
    return message



"""Travail d'analyse du TP

1. En quoi HTTP convient-il bien à cette application ?
Comme le protocole HTTP suit un modèle "Requête/Réponse" initié par le client, cela correspond parfaitement à une messagerie "classique":
L'utilisateur demande à voir sa boîte de réception (GET). L'utilisateur soumet un formulaire lorsqu'il veut envoyer un message (POST).
Le client n'a besoin d'informations que lorsqu'il les demande explicitement. D'où l'utilité d'utiliser HTTP.

2. Quelles limites apparaissent si l’on veut une vraie messagerie “vivante” ?

On a vu en cours que HTTP était unidirectionnel (le serveur ne peut pas parler au client directement) et sans état.
De plus, en HTTP, le client devrait spammer le serveur de requêtes toutes les secondes pour vérifier qu'un message n'est pas arrivé, ce qui surcharge le réseau et le serveur.
Enfin, il est impossible de pousser une notification "Lu" depuis le serveur vers le client sans que le client ne recharge ou ne redemande explicitement la donnée. 
D'où les limites de ce procédé.


3. Quelle solution pourrait-on introduire ensuite ?
Pour passer en temps réel, on a vu en cours que WebSocket était une bonne approche. 
En regardant la documentation de WebSocket, contrairement à HTTP, WebSocket maintient une connexion persistante et bidirectionnelle ouverte entre le client et le serveur. 
Ainsi, dès qu'un utilisateur envoie un message à un autre utilisateur, le serveur (qui a gardé la connexion de l'autre utilisateur ouverte) peut "pousser" le message directement 
sur l'écran de l'utilisateur qui reçoit le message, sans que ce dernier n'ait rien à demander. Ce qui s'avère être tout de même beaucoup plus utile pour discuter en temps réel. """
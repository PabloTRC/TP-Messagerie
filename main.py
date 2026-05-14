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
    if message.sender_id == message.receiver_id: #on ne peut pas s'envoyer à soi-même
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous envoyer un message à vous-même.")
    
    sender = session.get(User, message.sender_id)
    receiver = session.get(User, message.receiver_id)
    
    if not sender or not receiver: #Expéditeur et destinataire existe
        raise HTTPException(status_code=404, detail="Expéditeur ou destinataire introuvable.")

    db_message = Message.model_validate(message)
    session.add(db_message)
    session.commit()
    session.refresh(db_message)
    return db_message

@app.get("/users/{user_id}/inbox", response_model=List[MessageRead])
def read_inbox(
    user_id: int, 
    session: Session = Depends(get_session),
    unread_only: bool = False,         # Filtre 1 (Partie 5)
    limit: int = Query(default=20, le=100), # Amélioration : Pagination (Partie 5)
    offset: int = 0
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
    
    query = select(Message).where(Message.receiver_id == user_id)
    
    if unread_only:
        query = query.where(Message.is_read == False)
        
    query = query.order_by(Message.created_at.desc()).offset(offset).limit(limit)
    return session.exec(query).all()

@app.get("/users/{user_id}/sent", response_model=List[MessageRead])
def read_sent_messages(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
    
    query = select(Message).where(Message.sender_id == user_id).order_by(Message.created_at.desc())
    return session.exec(query).all()

@app.get("/messages/{message_id}", response_model=MessageRead)
def read_message(message_id: int, session: Session = Depends(get_session)):
    message = session.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message non trouvé.")
    return message

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




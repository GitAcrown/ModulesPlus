import asyncio
import os
from .utils import checks
import discord
from collections import namedtuple
from __main__ import send_cmd_help
from discord.ext import commands
import time
import operator
import random
from .utils.dataIO import fileIO, dataIO


class Hanged:
    """Jeu du pendu [1 - 8 joueurs]"""
    def __init__(self, bot):
        self.bot = bot
        self.data = dataIO.load_json("data/hanged/data.json")
        self.session = {}
        self.wallet = self.bot.get_cog("Wallet").api

    def save(self):
        fileIO("data/hanged/data.json", "save", self.data)
        return True

    def get_theme(self, nom: str):
        """Renvoie un thème"""
        themes = {"general": ['ANGLE', 'ARMOIRE', 'BANC', 'BUREAU', 'CABINET', 'CARREAU', 'CHAISE', 'CLASSE', 'CLEF',
                          'COIN', 'COULOIR', 'DOSSIER', 'EAU', 'ECOLE', 'ENTRER', 'ESCALIER', 'ETAGERE', 'EXTERIEUR',
                          'FENETRE', 'INTERIEUR', 'LAVABO', 'LIT', 'MARCHE', 'MATELAS', 'MATERNELLE', 'MEUBLE',
                          'MOUSSE', 'MUR', 'PELUCHE', 'PLACARD', 'PLAFOND', 'PORTE', 'POUBELLE', 'RADIATEUR', 'RAMPE',
                          'RIDEAU', 'ROBINET', 'SALLE', 'SALON', 'SERRURE', 'SERVIETTE', 'SIEGE', 'SIESTE', 'SILENCE',
                          'SOL', 'SOMMEIL', 'SONNETTE', 'SORTIE', 'TABLE', 'TABLEAU', 'TABOURET', 'TAPIS', 'TIROIR',
                          'TOILETTE', 'VITRE', 'ALLER', 'AMENER', 'APPORTER', 'APPUYER', 'ATTENDRE', 'BAILLER',
                          'COUCHER', 'DORMIR', 'ECLAIRER', 'EMMENER', 'EMPORTER', 'ENTRER', 'FERMER', 'FRAPPER',
                          'INSTALLER', 'LEVER', 'OUVRIR', 'PRESSER', 'RECHAUFFER', 'RESTER', 'SONNER', 'SORTIR',
                          'VENIR', 'ABSENT', 'ASSIS', 'BAS', 'HAUT', 'PRESENT', 'GAUCHE', 'DROITE', 'DEBOUT',
                          'DEDANS', 'DEHORS', 'FACE', 'LOIN', 'PRES', 'TARD', 'TOT', 'APRES', 'AVANT', 'CONTRE',
                          'DANS', 'DE', 'DERRIERE', 'DEVANT', 'DU', 'SOUS', 'SUR', 'CRAYON', 'STYLO', 'FEUTRE',
                          'MINE', 'GOMME', 'DESSIN', 'COLORIAGE', 'RAYURE', 'PEINTURE', 'PINCEAU', 'COULEUR',
                          'CRAIE', 'PAPIER', 'FEUILLE', 'CAHIER', 'CARNET', 'CARTON', 'CISEAUX', 'DECOUPAGE',
                          'PLIAGE', 'PLI', 'COLLE', 'AFFAIRE', 'BOITE', 'CASIER', 'CAISSE', 'TROUSSE', 'CARTABLE',
                          'JEU', 'JOUET', 'PION', 'DOMINO', 'PUZZLE', 'CUBE', 'PERLE', 'CHOSE', 'FORME', 'CARRE',
                          'ROND', 'PATE', 'MODELER', 'TAMPON', 'LIVRE', 'HISTOIRE', 'BIBLIOTHEQUE', 'IMAGE', 'ALBUM',
                          'TITRE', 'CONTE', 'DICTIONNAIRE', 'MAGAZINE', 'CATALOGUE', 'PAGE', 'LIGNE', 'MOT',
                          'ENVELOPPE', 'ETIQUETTE', 'CARTE', 'APPEL', 'AFFICHE', 'ALPHABET', 'APPAREIL', 'CAMESCOPE',
                          'CASSETTE', 'CHAINE', 'CHANSON', 'CHIFFRE', 'CONTRAIRE', 'DIFFERENCE', 'DOIGT', 'ECRAN',
                          'ECRITURE', 'FILM', 'FOIS', 'FOI', 'IDEE', 'INSTRUMENT', 'INTRUS', 'LETTRE', 'LISTE',
                          'MAGNETOSCOPE', 'MAIN', 'MICRO', 'MODELE', 'MUSIQUE', 'NOM', 'NOMBRE', 'ORCHESTRE',
                          'ORDINATEUR', 'PHOTO', 'POINT', 'POSTER', 'POUCE', 'PRENOM', 'QUESTION', 'RADIO', 'SENS',
                          'TAMBOUR', 'TELECOMMANDE', 'TELEPHONE', 'TELEVISION', 'TRAIT', 'TROMPETTE', 'VOIX',
                          'XYLOPHONE', 'ZERO', 'CHANTER', 'CHERCHER', 'CHOISIR', 'CHUCHOTER', 'COLLER', 'COLORIER',
                          'COMMENCER', 'COMPARER', 'COMPTER', 'CONSTRUIRE', 'CONTINUER', 'COPIER', 'COUPER',
                          'DECHIRER', 'DECOLLER', 'DECORER', 'DECOUPER', 'DEMOLIR', 'DESSINER', 'DIRE', 'DISCUTER',
                          'ECOUTER', 'ECRIRE', 'EFFACER', 'ENTENDRE', 'ENTOURER', 'ENVOYER', 'FAIRE', 'FINIR',
                          'FOUILLER', 'GOUTER', 'IMITER', 'LAISSER', 'LIRE', 'METTRE', 'MONTRER', 'OUVRIR', 'PARLER',
                          'PEINDRE', 'PLIER', 'POSER', 'PRENDRE', 'PREPARER', 'RANGER', 'RECITER', 'RECOMMENCER',
                          'REGARDER', 'REMETTRE', 'REPETER', 'REPONDRE', 'SENTIR', 'SOULIGNER', 'TAILLER', 'TENIR',
                          'TERMINER', 'TOUCHER', 'TRAVAILLER', 'TRIER', 'AMI', 'ATTENTION', 'CAMARADE', 'COLERE',
                          'COPAIN', 'COQUIN', 'DAME', 'DIRECTEUR', 'DIRECTRICE', 'DROIT', 'EFFORT', 'ELEVE', 'ENFANT',
                          'FATIGUE', 'FAUTE', 'FILLE', 'GARCON', 'GARDIEN', 'MADAME', 'MAITRE', 'MAITRESSE',
                          'MENSONGE', 'ORDRE', 'PERSONNE', 'RETARD', 'JOUEUR', 'SOURIRE', 'TRAVAIL', 'AIDER',
                          'DEFENDRE', 'DESOBEIR', 'DISTRIBUER', 'ECHANGER', 'EXPLIQUER', 'GRONDER', 'OBEIR', 'OBLIGER',
                          'PARTAGER', 'PRETER', 'PRIVER', 'PROMETTRE', 'PROGRES', 'PROGRESSER', 'PUNIR', 'QUITTER',
                          'RACONTER', 'EXPLIQUER', 'REFUSER', 'SEPARER', 'BLOND', 'BRUN', 'CALME', 'CURIEUX',
                          'DIFFERENT', 'DOUX', 'ENERVER', 'GENTIL', 'GRAND', 'HANDICAPE', 'INSEPARABLE', 'JALOUX',
                          'MOYEN', 'MUET', 'NOIR', 'NOUVEAU', 'PETIT', 'POLI', 'PROPRE', 'ROUX', 'SAGE', 'SALE',
                          'SERIEUX', 'SOURD', 'TRANQUILLE', 'ARROSOIR', 'ASSIETTE', 'BALLE', 'BATEAU', 'BOITE',
                          'BOUCHON', 'BOUTEILLE', 'BULLES', 'CANARD', 'CASSEROLE', 'CUILLERE', 'CUVETTE', 'DOUCHE',
                          'ENTONNOIR', 'GOUTTES', 'LITRE', 'MOULIN', 'PLUIE', 'POISSON', 'PONT', 'POT', 'ROUE', 'SAC',
                          'PLASTIQUE', 'SALADIER', 'SEAU', 'TABLIER', 'TASSE', 'TROUS', 'VERRE', 'AGITER', 'AMUSER',
                          'ARROSER', 'ATTRAPER', 'AVANCER', 'BAIGNER', 'BARBOTER', 'BOUCHER', 'BOUGER', 'DEBORDER',
                          'DOUCHER', 'ECLABOUSSER', 'ESSUYER', 'ENVOYER', 'COULER', 'PARTIR', 'FLOTTER', 'GONFLER',
                          'INONDER', 'JOUER', 'LAVER', 'MELANGER', 'MOUILLER', 'NAGER', 'PLEUVOIR', 'PLONGER',
                          'POUSSER', 'POUVOIR', 'PRESSER', 'RECEVOIR', 'REMPLIR', 'RENVERSER', 'SECHER', 'SERRER',
                          'SOUFFLER', 'TIRER', 'TOURNER', 'TREMPER', 'VERSER', 'VIDER', 'VOULOIR', 'AMUSANT', 'CHAUD',
                          'FROID', 'HUMIDE', 'INTERESSANT', 'MOUILLE', 'SEC', 'TRANSPARENT', 'MOITIE', 'AUTANT',
                          'BEAUCOUP', 'ENCORE', 'MOINS', 'PEU', 'PLUS', 'TROP', 'ANORAK', 'ARC', 'BAGAGE', 'BAGUETTE',
                          'BARBE', 'BONNET', 'BOTTE', 'BOUTON', 'BRETELLE', 'CAGOULE', 'CASQUE', 'CASQUETTE',
                          'CEINTURE', 'CHAPEAU', 'CHAUSSETTE', 'CHAUSSON', 'CHAUSSURE', 'CHEMISE', 'CIGARETTE', 'COL',
                          'COLLANT', 'COURONNE', 'CRAVATE', 'CULOTTE', 'ECHARPE', 'EPEE', 'FEE', 'FLECHE', 'FUSIL',
                          'GANT', 'HABIT', 'JEAN', 'JUPE', 'LACET', 'LAINE', 'LINGE', 'LUNETTES', 'MAGICIEN', 'MAGIE',
                          'MAILLOT', 'MANCHE', 'MANTEAU', 'MOUCHOIR', 'MOUFLE', 'NOEUD', 'PAIRE', 'PANTALON', 'PIED',
                          'POCHE', 'PRINCE', 'PYJAMA', 'REINE', 'ROBE', 'ROI', 'RUBAN', 'SEMELLE', 'SOLDAT', 'SORCIERE']}
        if nom.lower() in themes:
            return themes[nom.lower()]
        return []

    def get_system(self, server: discord.Server):
        """Données système du jeu sur le serveur"""
        if server.id not in self.data:
            self.data[server.id] = {"encode_char": "•",
                                    "leaderboard": [],
                                    "leaderboard_since": time.time()}
            self.save()
        return self.data[server.id]

    def get_session(self, server: discord.Server, reset: bool = False):
        """Charge les données de la session en cours"""
        if server.id not in self.session or reset:
            self.session[server.id] = {"on": False,
                                       "players": {},
                                       "vies": 0,
                                       "avancement": [],
                                       "propose":[],
                                       "mot": None,
                                       "themes": [],
                                       "channel": None}
        return self.session[server.id]

    def load_themes(self, themes):
        """Charge les modules demandés"""
        mots = []
        double = []
        themes = themes[:3]
        for theme in themes:
            get = self.get_theme(theme.lower())
            if get:
                if theme not in double:
                    double.append(theme)
                    mots.extend(get)
        return mots

    def get_mot(self, server: discord.Server, words: list):
        """Génère un objet Mot()"""
        symb = self.get_system(server)["encode_char"]
        words = [w for w in words if len(w) >= 4]
        mot = random.choice(words)
        Mot = namedtuple('Mot', ['literal', 'lettres', 'encode'])
        return Mot(mot.upper(), [self.normal(l).upper() for l in mot], [n for n in symb * len(mot)])

    def normal(self, txt):
        ch1 = "àâçéèêëîïôöùûüÿ"
        ch2 = "aaceeeeiioouuuy"
        final = []
        for l in txt.lower():
            if l in ch1:
                final.append(ch2[ch1.index(l)])
            else:
                final.append(l)
        return "".join(final)

    def approx(self, s1, s2):
        if len(s1) < len(s2):
            m = s1
            s1 = s2
            s2 = m
        if len(s2) == 0:
            return len(s1)
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[
                                 j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def bottomtext(self, status: str):
        if status.lower() == "good":
            return "**{}**".format(random.choice(["Exact", "Bien joué", "Excellent", "Absolument", "Correct"]))
        elif status.lower() == "bad":
            return "**{}**".format(random.choice(["Loupé", "Dommage", "Incorrect", "Nope", "C'est pas ça"]))
        else:
            return "**{}**".format(random.choice(["Désolé", "Invalide", "Oups...", "Pardon ?"]))

    def verif(self, msg: discord.Message):
        session = self.get_session(msg.server)
        if session["on"]:
            if not msg.author.bot:
                if msg.author.id in session["players"]:
                    if msg.content.lower()[0] not in ["?", "!", ";;", "&", "\\", ":", ">", ";", "."]:
                        if len(msg.content.split(" ")) == 1:
                            return True
        return False

    def gen_embed(self, server: discord.Server):
        session = self.get_session(server)
        if session["on"]:
            txt = "**Vies** — {}\n".format("\💟" * session["vies"])
            txt += "**Joueurs** — {}\n".format(" ".join(["`{}`".format(server.get_member(i).name) for i in session["players"]]))
            txt += "\n[{}]".format(" ".join(session["avancement"]))

            em = discord.Embed(title="Pendu — {}".format(", ".join(session["themes"])), description=txt, color=0x7289DA)
            if session["propose"]:
                em.set_footer(text="{}".format(" ".join(session["propose"])))
            return em
        return False

    def msg_bye(self):
        heure = int(time.strftime("%H", time.localtime()))
        if 6 <= heure <= 12:
            return "Bonne matinée !"
        elif 13 <= heure <= 17:
            return "Bonne après-midi !"
        elif 18 <= heure <= 22:
            return "Bonne soirée !"
        else:
            return "Bonne nuit !"

    @commands.command(aliases=["hanged"], pass_context=True, no_pm=True)
    async def pendu(self, ctx, *themes):
        """Lance une partie de Pendu avec les thèmes sélectionnés"""
        server = ctx.message.server
        author = ctx.message.author
        if not themes:
            themes = ["general"]
        session, sys = self.get_session(server), self.get_system(server)
        if await self.wallet.sign_up(author):
            if not session["on"]:
                mots = self.load_themes(themes)
                if mots:
                    session = self.get_session(server, True) # Reset
                    mot = self.get_mot(server, mots)
                    session["themes"] = [i.title() for i in themes]
                    session["vies"] = 6 + len(themes)
                    session["players"][author.id] = {"+": 0, "-": 0}
                    session["timeout"] = 0
                    session["mot"] = mot
                    session["avancement"] = mot.encode
                    session["channel"] = ctx.message.channel
                    session["on"] = True
                    if self.gen_embed(server):
                        await self.bot.say(embed=self.gen_embed(server))
                        await asyncio.sleep(0.1)

                    while session["vies"] > 0 and session["avancement"] != mot.lettres and session["timeout"] <= 120:
                        await asyncio.sleep(0.5)
                        session["timeout"] += 1

                    session["on"] = False
                    if session["timeout"] > 120:
                        if session["avancement"]:
                            msg = "Le mot était **{}**\nVos soldes n'ont pas été affectés.".format(mot.literal)
                            em = discord.Embed(title="Pendu — Partie annulée", description=msg, color=0xe15555)
                            em.set_footer(text=self.msg_bye())
                            await self.bot.say(embed=em)
                            self.get_session(server, True)
                        return
                    if not session["vies"]:
                        msg = "Le mot était **{}**".format(mot.literal)
                        unord = []
                        for p in session["players"]:
                            perte = session["players"][p]["-"]
                            unord.append([perte, p])
                        classt = sorted(unord, key=operator.itemgetter(0), reverse=True)
                        txt = ""
                        for u in classt:
                            user = server.get_member(u[1])
                            self.wallet.remove_credits(user, u[0], "Partie perdue au pendu", True, "pendu")
                            txt += "*{}*  — **-{}**g\n".format(user.name, u[0])
                        em = discord.Embed(title="Pendu — Échec", description=msg, color=0xe15555)
                        em.add_field(name="Perdants", value=txt)
                        em.set_footer(text=self.msg_bye())
                        await self.bot.say(embed=em)
                        self.get_session(server, True)
                        return
                    elif "".join(session["avancement"]) == mot.literal:
                        msg = "***Bravo !*** Le mot est bien **{}**".format(mot.literal)
                        unord = []
                        for p in session["players"]:
                            bonus = session["players"][p]["+"]
                            unord.append([bonus, p])
                        classt = sorted(unord, key=operator.itemgetter(0), reverse=True)
                        txt = ""
                        for u in classt:
                            user = server.get_member(u[1])
                            self.wallet.add_credits(user, u[0], "Partie perdue au pendu", "pendu")
                            txt += "*{}*  — **+{}**g\n".format(user.name, u[0])
                        em = discord.Embed(title="Pendu — Victoire", description=msg, color=0x84e155)
                        em.add_field(name="Gagnants", value=txt)
                        em.set_footer(text=self.msg_bye())
                        await self.bot.say(embed=em)
                        self.get_session(server, True)
                        return
                    else:
                        await self.bot.say("**Partie arrêtée** — Vos comptes ne sont pas affectés")
                        self.get_session(server, True)
                        return
                else:
                    await self.bot.say("**Erreur** — Thèmes inexistants ou invalides")
            elif author.id not in session["players"]:
                session["players"][author.id] = {"+": 0, "-": 0}
                em = discord.Embed(description="**{}** a rejoint la partie !".format(author.name), color=0x7289DA)
                await self.bot.say(embed=em)
            elif themes[0].lower() == "stop":
                await self.bot.say("**Patientez...**")
                session["timeout"] = 999
                await asyncio.sleep(3)
                self.get_session(server, True)
                await self.bot.say("**Partie stoppée de force avec succès**")
            else:
                await self.bot.say("**Refusé** — Finissez la partie en cours sur {} ou faîtes `;pendu stop`".format(session["channel"].name))
        else:
            await self.bot.say("Vous avez besoin d'un compte Wallet pour jouer au pendu")

    async def grab_msg(self, message):
        author = message.author
        server = message.server
        content = message.content
        if hasattr(author, "server"):
            if self.verif(message):
                sys, session = self.get_system(server), self.get_session(server)
                if session["channel"] == message.channel:
                    mot = session["mot"]
                    content = self.normal(content).upper()
                    indexes = lambda c: [[i, x] for i, x in enumerate(mot.lettres) if self.normal(x).upper() == c]
                    if content == "STOP":
                        await self.bot.send_message(message.channel, "**Partie terminée prématurément** — "
                                                                     "Vos soldes ne sont pas affectés.")
                        self.get_session(server, True)
                        return
                    elif len(content) == 1:
                        if content in mot.lettres:
                            if content not in session["propose"]:
                                for l in indexes(content):
                                    session["avancement"][l[0]] = l[1].upper()
                                session["propose"].append(content)
                                count = mot.lettres.count(content)
                                session["players"][author.id]["+"] += count
                                if count > 1:
                                    phx = "{} lettres trouvées !".format(count)
                                else:
                                    phx = "Une lettre trouvée !"
                                await self.bot.send_message(message.channel, self.bottomtext("good") + " — " + phx)
                                session["timeout"] = 0
                                em = self.gen_embed(server)
                                if em:
                                    await self.bot.send_message(message.channel, embed=em)
                            else:
                                await self.bot.send_message(message.channel, self.bottomtext("neutre") + " — " +
                                                            "Vous avez déjà trouvé cette lettre !")
                                session["timeout"] = 0
                                em = self.gen_embed(server)
                                if em:
                                    await self.bot.send_message(message.channel, embed=em)
                        else:
                            if content in session["propose"]:
                                await self.bot.send_message(message.channel, self.bottomtext("neutre") + " — " +
                                                            "Vous avez déjà proposé cette lettre !")
                                session["timeout"] = 0
                                em = self.gen_embed(server)
                                if em:
                                    await self.bot.send_message(message.channel, embed=em)
                            else:
                                session["vies"] -= 1
                                session["players"][author.id]["-"] -= 1
                                session["propose"].append(content)
                                await self.bot.send_message(message.channel, self.bottomtext("neutre") + " — " +
                                                            "Cette lettre ne s'y trouve pas !")
                                session["timeout"] = 0
                                em = self.gen_embed(server)
                                if em:
                                    await self.bot.send_message(message.channel, embed=em)
                    elif content == "".join(mot.literal):
                        session["players"][author.id]["+"] += 2 * session["avancement"].count(sys["encode_char"])
                        session["avancement"] = mot.lettres
                    else:
                        session["vies"] -= 1
                        session["players"][author.id]["-"] -= 2
                        await self.bot.send_message(message.channel, self.bottomtext("bad") + " — " +
                                                    "Ce n'est pas le mot recherché")
                        session["timeout"] = 0
                        em = self.gen_embed(server)
                        if em:
                            await self.bot.send_message(message.channel, embed=em)


def check_folders():
    if not os.path.exists("data/hanged/"):
        print("Creation du dossier Jeu du hanged...")
        os.makedirs("data/hanged")


def check_files():
    if not os.path.isfile("data/hanged/data.json"):
        print("Création du fichier Jeu du hanged")
        fileIO("data/hanged/data.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Hanged(bot)
    bot.add_listener(n.grab_msg, "on_message")
    bot.add_cog(n)
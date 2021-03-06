import asyncio
import os
import random
import re
import time
from copy import deepcopy

import discord
from __main__ import send_cmd_help
from discord.ext import commands

from .utils import checks
from .utils.dataIO import fileIO, dataIO

items_list = {
  "MINERAI":{
    "fer": {"id": "fer", "name": "Fer", "value": 5, "max": 15, "rare": 1, "energie": 1, "imageurl": "https://i.imgur.com/DT5UFL9.png"},
    "cuivre": {"id": "cuivre", "name": "Cuivre", "value": 8, "max": 12, "rare": 1, "energie": 1, "imageurl": "https://i.imgur.com/E04CMpW.png"},
    "argent": {"id": "argent", "name": "Argent", "value": 18, "max": 10, "rare": 2, "energie": 3, "imageurl": "https://i.imgur.com/5vpIa7g.png"},
    "cobalt": {"id": "cobalt", "name": "Cobalt", "value": 25, "max": 10, "rare": 2, "energie": 3, "imageurl": "https://i.imgur.com/zmEKTiy.png"},
    "or": {"id": "or", "name": "Or", "value": 35, "max": 9, "rare": 2, "energie": 4, "imageurl": "https://i.imgur.com/yisG8jH.png"},
    "platine": {"id": "platine", "name": "Platine", "value": 27, "max": 9, "rare": 2, "energie": 3, "imageurl": "https://i.imgur.com/FQVNapP.png"},
    "rubis": {"id": "rubis", "name": "Rubis", "value": 60, "max": 7, "rare": 3, "energie": 8, "imageurl": "https://i.imgur.com/gRRFpfM.png"},
    "plutonium": {"id": "plutonium", "name": "Plutonium", "value": 75, "max": 7, "rare": 3, "energie": 12, "imageurl": "https://i.imgur.com/yCLEbgZ.png"},
    "diamant": {"id": "diamant", "name": "Diamant", "value": 100, "max": 5, "rare": 3, "energie": 10, "imageurl": "https://i.imgur.com/vGRv297.png"},
    "adamantium": {"id": "adamantium", "name": "Adamantium", "value": 600, "max": 3, "rare": 4, "energie": 22, "imageurl": "https://i.imgur.com/QiIN42H.png"},
    "orichalque": {"id": "orichalque", "name": "Orichalque", "value": 220, "max": 4, "rare": 4, "energie": 15, "imageurl": "https://i.imgur.com/TQOVxTp.png"},
    "mithril": {"id": "mithril", "name": "Mithril", "value": 160, "max": 5, "rare": 4, "energie": 12, "imageurl": "https://i.imgur.com/HxZVq1H.png"}
  },
  "UNIQUE":{
    "pespace": {"id": "pespace", "name": "Pierre de l'Espace", "qte": 1},
    "pesprit": {"id": "pesprit", "name": "Pierre de l'Esprit", "qte": 1},
    "pame": {"id": "pame", "name": "Pierre de l'Âme", "qte": 1},
    "prealite": {"id": "prealite", "name": "Pierre de la Réalité", "qte": 1},
    "ptemps": {"id": "ptemps", "name": "Pierre du Temps", "qte": 1},
    "ppouvoir": {"id": "ppouvoir", "name": "Pierre du Pouvoir", "qte": 1}
  },
  "ITEM":{
    "detector": {"id": "detector", "name": "Détecteur de minerai", "value": 50, "qte": 1, "desc": "Permet de recevoir une notification 10s avant qu'une entité apparaisse"},
    "booster": {"id": "booster", "name": "Booster de pioche", "value": 75, "qte": 1, "desc": "Permet d'obtenir davantage d'unités lors d'un minage (x1.5 à x2)"},
    "barrenrj": {"id": "barrenrj", "name": "Barre énergétique", "value": 150, "qte": 3, "desc": "Recharge l'énergie au maximum (\\⚡)"},
    "coeurnrj": {"id":  "coeurnrj", "name":  "Coeur énergétique", "value": 2500, "qte": 1, "desc": "Augmente de manière permanente l'énergie maximale (\\⚡)"},
    "poche": {"id":  "poche", "name":  "Poche supplémentaire", "value": 2000, "qte": 1, "desc": "Augmente de manière permanente la capacité de l'inventaire (+20)"}
  }
}

# "palmade": {"id":  "palmade", "name":  "Pierre Palmade", "value": 50, "qte": 1, "desc": "???"}

class Cobalt:
    """Minez, récoltez, enrichissez-vous !"""

    def __init__(self, bot):
        self.bot = bot
        self.data = dataIO.load_json("data/cobalt/data.json")
        self.items = items_list
        self.glob = {"buy_queue": {}}
        self.heartbeat = {}

    def save(self):
        fileIO("data/cobalt/data.json", "save", self.data)
        return True

    def get_heartbeat(self, server):
        if server.id not in self.heartbeat:
            self.heartbeat[server.id] = {"ack": 0,
                                         "limit": random.randint(50, 300),
                                         "item": False,
                                         "journal": [],
                                         "user_nrj": {}}
        return self.heartbeat[server.id]

    def cash_api(self):
        try:
            cash = self.bot.get_cog("Cash").api
            return cash
        except:
            return None

    def get_energy_sess(self, user: discord.Member):
        hb = self.get_heartbeat(user.server)
        if user.id not in hb["user_nrj"]:
            hb["user_nrj"][user.id] = 0
        return hb["user_nrj"][user.id]

    def add_log(self, server: discord.Server, text: str):
        """Ajoute un log au serveur"""
        journal = self.get_heartbeat(server)["journal"]
        journal.append([time.time(), text])
        return True

    def get_server(self, server: discord.Server):
        if server.id not in self.data:
            self.data[server.id] = {"SYS": {"channels": [],
                                            "maxfreq": 200},
                                    "USERS": {}}
            self.save()
        return self.data[server.id]

    def get_user(self, user: discord.Member):
        """Renvoie le profil Cobalt du joueur"""
        data = self.get_server(user.server)["USERS"]
        if user.id not in data:
            data[user.id] = {"minerais": {},
                             "uniques": {},
                             "items": {},
                             "energie": 30,
                             "max_energie": 30,
                             "max_capacite": 200,
                             "status": [],
                             "ban": False}
            self.save()

        if "max_capacite" not in data[user.id]:
            data[user.id]["max_capacite"] = 200
            self.save()
        return data[user.id] if data[user.id]["ban"] is False else {}

    def ban_user(self, user: discord.Member):
        data = self.get_server(user.server)["USERS"]
        if user.id in data:
            data[user.id]["ban"] = True
            self.save()
            return True
        return False

    def unban_user(self, user: discord.Member):
        data = self.get_server(user.server)["USERS"]
        if user.id in data:
            data[user.id]["ban"] = False
            self.save()
            return True
        return False

    def add_item(self, user: discord.Member, **item):
        """Ajoute un item/équipement à un joueur"""
        data = self.get_user(user)
        try:
            if item["type"] == "MINERAI":
                sac = sum([data["minerais"][i]["qte"] for i in data["minerais"]])
                if sac + item["qte"] <= data["max_capacite"]:
                    inv = data["minerais"]
                    if item["id"] in inv:
                        itemid = item["id"]
                        inv[itemid]["qte"] += item["qte"]
                    else:
                        itemid = item["id"]
                        inv[itemid] = {"name": item["name"], "qte": item["qte"]}
                else:
                    return False
            elif item["type"] == "UNIQUE":
                inv = data["uniques"]
                if item["id"] in inv:
                    itemid = item["id"]
                    inv[itemid]["qte"] += item["qte"]
                else:
                    itemid = item["id"]
                    inv[itemid] = {"name": item["name"], "qte": item["qte"]}
            else:
                inv = data["items"]
                if item["id"] in inv:
                    itemid = item["id"]
                    inv[itemid]["qte"] += item["qte"]
                else:
                    itemid = item["id"]
                    cache = {}
                    if "cache" in item:
                        cache = item["cache"]
                    inv[itemid] = {"name": item["name"], "qte": item["qte"], "cache": cache}
            self.save()
            return True
        except ValueError as e:
            print("COBALT - Impossible d'ajouter un item : " + str(e))
            return False

    def del_item(self, user: discord.Member, itemid, qte):
        """Retire un item du membre"""
        data = self.get_user(user)
        if data:
            item = self.get_item(itemid)
            if item["type"] == "MINERAI":
                if itemid in data["minerais"]:
                    if qte < data["minerais"][itemid]["qte"]:
                        data["minerais"][itemid]["qte"] -= qte
                        self.save()
                        return True
                    elif qte >= data["minerais"][itemid]["qte"]:
                        del data["minerais"][itemid]
                        self.save()
                        return True
                return False
            if item["type"] == "UNIQUE":
                if itemid in data["uniques"]:
                    del data["uniques"][itemid]
                    self.save()
                    return True
                return False
            if item["type"] == "ITEM":
                if itemid in data["items"]:
                    if qte < data["items"][itemid]["qte"]:
                        data["items"][itemid]["qte"] -= qte
                        self.save()
                        return True
                    elif qte >= data["items"][itemid]["qte"]:
                        del data["items"][itemid]
                        self.save()
                        return True
                return False
        return False

    def reset_user_type(self, user: discord.Member, type: str):
        data = self.get_user(user)
        if data:
            data[type] = {}
            self.save()
            return True
        return False

    def get_item(self, itemid: str):
        """Retourne le dict de l'item demandé"""
        for cat in self.items:
            if itemid in self.items[cat]:
                item = deepcopy(self.items[cat][itemid])
                item["type"] = cat
                return item
        return {}

    def get_user_items(self, user: discord.Member, type: str):
        """Retourne les items d'une certaine catégorie appartenant à un membre"""
        user = self.get_user(user)
        if user:
            search = {}
            if type.lower() == "unique":
                for u in user["minerais"]:
                    if user["minerais"][u]["unique"]:
                        search[u] = user["minerais"][u]
                return search
            elif type.lower() == "minerai":
                for u in user["minerais"]:
                    if not user["minerais"][u]["unique"]:
                        search[u] = user["minerais"][u]
                return search
            else:
                search = deepcopy(user["items"])
                return search
        return {}

    def own_item(self, user: discord.Member, itemid, cache: dict = None):
        """Vérifie si le joueur possède l'item demandé (y compris le cache)"""
        data = self.get_user(user)
        if itemid in data["minerais"]: return True
        if itemid in data["uniques"]: return True
        elif itemid in data["items"]:
            if cache:
                for e in cache:
                    if e in data["items"][itemid]["cache"]:
                        if cache[e] != data["items"][itemid]["cache"][e]:
                            return False
                        else:
                            pass
                    else:
                        return False
            return True
        return False

    def have_status(self, user: discord.Member, status: str, consomme: bool = False):
        """Vérifie qu'un membre possède bien le statut et le consomme si l'option est activée"""
        data = self.get_user(user)
        if data:
            if status.lower() in data["status"]:
                if consomme:
                    data["status"].remove(status)
                    self.save()
                return True
        return False

    def get_users_with_status(self, server: discord.Server, status: str):
        """Retrouve tous les membres du serveur qui bénéficient d'un certain statut"""
        users = self.get_server(server)["USERS"]
        liste = []
        for u in users:
            if status.lower() in users[u]["status"]:
                liste.append(u)
        return liste

    async def obtain_item(self, channel: discord.Channel, itemid):
        """Affiche l'item sur un channel afin qu'il puisse être miné"""
        item = self.get_item(itemid)
        server = channel.server
        hb = self.get_heartbeat(server)
        cash = self.cash_api()
        cur = cash.get_currency(server)
        if item["type"] is "MINERAI":
            await asyncio.sleep(random.randint(1, 4))
            qte = random.randint(1, item["max"])
            phrase = random.choice(["**{0}** (x{1}) est apparu !\nCliquez sur `⛏` pour le miner !",
                                    "**{0}** (x{1}) vient d'apparaître !\nCliquez sur `⛏` pour le miner !",
                                    "{1} unité(s) de **{0}** ont été exposés par le vent !\nCliquez sur `⛏` pour le miner !",
                                    "**{0}** (x{1}) vient d'être découvert !\nMinez-le avec `⛏` !"])
            em = discord.Embed(description=phrase.format(item["name"], qte), color=0x0047AB)
            if "imageurl" in item:
                em.set_thumbnail(url=item["imageurl"])
            em.set_footer(text="Coût en énergie = {}⚡".format(item["energie"]))

            detectors = self.get_users_with_status(server, "detector")
            if detectors:
                for u in detectors:
                    try:
                        user = server.get_member(u)
                        detem = discord.Embed(description="**Détecteur de minerais** • Un minerai **{}** se trouve sur {} "
                                                          "et va bientôt apparaître !".format(item["name"], channel.mention))
                        await self.bot.send_message(user, embed=detem)
                        self.get_user(user)["status"].remove("detector")
                    except:
                        pass
                await asyncio.sleep(10)

            def check(reaction, user):
                if not user.bot:
                    return True if self.get_user(user) else False
                return False

            notif = await self.bot.send_message(channel, embed=em)
            await asyncio.sleep(0.1)
            await self.bot.add_reaction(notif, "⛏")
            rep = await self.bot.wait_for_reaction(["⛏"], message=notif, timeout=120, check=check)
            if rep is None:
                await self.bot.delete_message(notif)
                return False
            elif rep.reaction.emoji == "⛏":
                data = self.get_user(rep.user)
                barreuse = True if self.own_item(rep.user, "barrenrj") else False

                if data["energie"] >= item["energie"]:
                    await self.bot.clear_reactions(notif)
                    foot = ""
                    if self.have_status(rep.user, "booster", True):
                        boost = random.choice([1.50, 1.75, 2])
                        qte = round(qte * boost)
                        foot = "Boosté = minerai x{}".format(boost)
                    p = random.choice(["**{0}** a été miné ! {1} en obtient {2} unité(s).",
                                                    "{1} obtient **{0}** (x{2}) !",
                                                    "Bien joué {1} ! Tu obtiens {2} unité(s) de **{0}**"])
                    em.description = p.format(item["name"], rep.user.mention, qte)
                    em.set_footer(text=foot)
                    em.set_thumbnail(url="")
                    await self.bot.edit_message(notif, embed=em)
                    data["energie"] -= item["energie"]
                    self.add_log(channel.server, "{} a obtenu **{}**".format(rep.user, item["name"]))

                    sac = sum([data["minerais"][i]["qte"] for i in data["minerais"]])
                    if sac + qte <= data["max_capacite"]:
                        self.add_item(rep.user, id=item["id"], type=item["type"], name=item["name"], qte=qte)
                    else:
                        qte = data["max_capacite"] - sac
                        if qte != 0:
                            self.add_item(rep.user, id=item["id"], type=item["type"], name=item["name"], qte=qte)
                            em = discord.Embed(title="Attention - Seuil maximum de l'inventaire atteint",
                                               description="Votre inventaire est plein ! Toutes les unités dépassant le seuil ont été jetées !")
                            await self.bot.send_message(rep.user, embed=em)
                        else:
                            em = discord.Embed(title="Attention - Inventaire plein",
                                               description="Votre inventaire est plein ! Vous n'avez pas pu récupérer les ressources minées !")
                            await self.bot.send_message(rep.user, embed=em)

                    await asyncio.sleep(16)
                    await self.bot.delete_message(notif)
                    return True
                elif barreuse:
                    data["energie"] = data["max_energie"]
                    self.del_item(rep.user, "barrenrj", 1)
                    self.save()
                    await self.bot.clear_reactions(notif)
                    foot = "Votre barre d'énergie a été utilisée automatiquement car vous n'aviez plus d'énergie"
                    if self.have_status(rep.user, "booster", True):
                        boost = random.choice([1.50, 1.75, 2])
                        qte *= boost
                        foot += " | Boosté = minerai x{}".format(boost)
                    p = random.choice(["**{0}** a été miné ! {1} en obtient {2} unité(s).",
                                       "{1} obtient **{0}** (x{2}) !",
                                       "Bien joué {1} ! Tu obtiens {2} unité(s) de **{0}**"])
                    em.description = p.format(item["name"], rep.user.mention, qte)
                    em.set_footer(text=foot)
                    em.set_thumbnail(url="")
                    await self.bot.edit_message(notif, embed=em)
                    data["energie"] -= item["energie"]
                    self.add_log(channel.server, "{} a obtenu **{}**".format(rep.user, item["name"]))

                    sac = sum([data["minerais"][i]["qte"] for i in data["minerais"]])
                    if sac + qte <= data["max_capacite"]:
                        self.add_item(rep.user, id=item["id"], type=item["type"], name=item["name"], qte=qte)
                    else:
                        qte = data["max_capacite"] - sac
                        if qte != 0:
                            self.add_item(rep.user, id=item["id"], type=item["type"], name=item["name"], qte=qte)
                            em = discord.Embed(title="Attention - Seuil maximum de l'inventaire atteint",
                                               description="Votre inventaire est plein ! Toutes les unités dépassant le seuil ont été jetées !")
                            await self.bot.send_message(rep.user, embed=em)
                        else:
                            em = discord.Embed(title="Attention - Inventaire plein",
                                               description="Votre inventaire est plein ! Vous n'avez pas pu récupérer les ressources minées !")
                            await self.bot.send_message(rep.user, embed=em)

                    await asyncio.sleep(16)
                    await self.bot.delete_message(notif)
                    return True
                else:
                    await self.bot.clear_reactions(notif)
                    perte = random.randint(50, 150)
                    em.description = "{} a tenté de miner **{}** mais n'avait pas assez d'énergie ! " \
                                     "Sa pioche est cassée.".format(rep.user, item["name"])
                    try:
                        cash.remove_credits(rep.user, perte, "Malus pioche cassée", ["cobalt"])
                        em.set_footer(text="Vous perdez {}.".format(cur.tformat(perte)))
                    except:
                        em.set_footer(text="Vous n'avez plus d'argent à perdre")
                    await self.bot.edit_message(notif, embed=em)
                    await asyncio.sleep(16)
                    await self.bot.delete_message(notif)
                    return True
            else:
                print("**Erreur COBALT** 01 - Le mauvais emoji a été utilisé alors qu'il n'est pas censé être détecté.")
        elif item == "UNIQUE":
            qte = random.randint(1, item["max"])
            phrase = random.choice(["**{0}** est apparu !\nCliquez sur `🖐` pour le ramasser !",
                                    "**{0}** vient d'apparaître !\nCliquez sur `🖐` pour ramasser l'item !"])
            em = discord.Embed(description=phrase.format(item["name"], qte), color=0x0047AB)
            if "imageurl" in item:
                em.set_thumbnail(url=item["imageurl"])

            notif = await self.bot.send_message(channel, embed=em)
            def check(reaction, user):
                if not user.bot:
                    return True if self.get_user(user) else False
                return False

            await asyncio.sleep(0.1)
            await self.bot.add_reaction(notif, "🖐")
            rep = await self.bot.wait_for_reaction(["🖐"], message=notif, timeout=120, check=check)
            if rep is None:
                await self.bot.delete_message(notif)
                return False
            elif rep.reaction.emoji == "🖐":
                await self.bot.clear_reactions(notif)
                p = random.choice(["{0} a ramassé **{1}** !", "{0} obtient **{1}** !"])
                em.description = p.format(rep.user.mention, item["name"])
                em.set_thumbnail(url="")
                await self.bot.edit_message(notif, embed=em)
                self.add_item(rep.user, id=item["id"], type=item["type"], name=item["name"], qte=qte)
                return True
            else:
                print("**Erreur COBALT** 02 - Le mauvais emoji a été utilisé alors qu'il n'est pas censé être détecté.")
        else:
            return False

    async def display_item(self, channel: discord.Channel, itemid, can_buy: bool = False, tempo: bool = False):
        """Affiche un item sur un salon"""
        item = self.get_item(itemid)
        cash = self.cash_api()
        cur = cash.get_currency(channel.server)
        txt = ""
        if item["type"] is "ITEM":
            typesymbol = "⚒"
            typetxt = "Equipement"
        elif item["type"] is "UNIQUE":
            typesymbol = "🔑"
            typetxt = "Objet unique"
            can_buy = False
        else:
            typesymbol = "📦"
            typetxt = "Minerai"
            can_buy = False
        if "desc" in item:
            txt += "*{}*\n\n".format(item["desc"])
        txt +=  "• **Type**: {}\n".format(typetxt)
        if "value" in item:
            txt += "• **Valeur**: {}{}".format(item["value"], "{}/unité".format(cur.symbole) if item["type"] != "ITEM" else cur.symbole)
        if "qte" in item:
            if item["qte"] > 1:
                txt += " (lot de {})".format(item["qte"])
        txt += "\n"
        if "rare" in item:
            txt += "• **Niveau de rareté**: {}\n".format(item["rare"])
        if "energie" in item:
            txt += "• **Energie nécessaire**: {}\⚡\n".format(item["energie"] if item["energie"] > 0 else "∞")
        em = discord.Embed(title=typesymbol + " " + item["name"], description=txt, color=0x0047AB)
        foot = "Partager — !{}$".format(itemid)
        if can_buy:
            foot += " | 🛒 = Acheter"
        em.set_footer(text=foot)
        if "imageurl" in item:
            em.set_thumbnail(url=item["imageurl"])
        msg = await self.bot.send_message(channel, embed=em)
        if can_buy:
            self.glob["buy_queue"][msg.id] = itemid
            await self.bot.add_reaction(msg, "🛒")
            if tempo:
                await asyncio.sleep(30)
                await self.bot.clear_reactions(msg)
                em.set_footer(text="Partager - !{}$".format(itemid))
                await self.bot.edit_message(msg, embed=em)
            return True
        else:
            return True

    async def buy_item(self, channel: discord.Channel, user: discord.Member, itemid, qte: int = None):
        item = self.get_item(itemid)
        data = self.get_user(user)
        cash = self.cash_api()
        cur = cash.get_currency(user.server)
        if item["type"] != "UNIQUE": # On ne peut pas acheter un item unique !
            if data:
                if not cash:
                    await self.bot.send_message(channel, "**Erreur** — Impossible de contacter le module *Cash*")
                    return
                if await cash.login(user):
                    if not qte:
                        while True:
                            txt = ""
                            if "desc" in item:
                                txt = "*{}*\n".format(item["desc"])
                            if "qte" in item:
                                if item["qte"] > 1:
                                    txt += "Vendu par lot de {}, chaque lot coûtant **{}**".format(item["qte"], cur.sformat(item["value"]))
                            else:
                                txt += "Chaque unité coûte **{}**".format(cur.sformat(item["value"]))
                            em = discord.Embed(description=txt, color=0x0047AB)
                            em.set_author(name="Achat — {} [{}]".format(item["name"], itemid),icon_url=user.avatar_url)
                            if "imageurl" in item:
                                em.set_thumbnail(url=item["imageurl"])
                            em.set_footer(text="» Combien en voulez-vous ? | \"Stop\" pour annuler")
                            msg = await self.bot.send_message(channel, embed=em)
                            rep = await self.bot.wait_for_message(channel=msg.channel, author=user, timeout=20)
                            if rep is None or rep.content.lower() in ["stop", "quitter", "q", "0"]:
                                em = discord.Embed(description="**Annulation de la transaction**",
                                                   color=0xa90000)
                                em.set_author(name="Achat — {} [{}]".format(item["name"], itemid),
                                              icon_url=user.avatar_url)
                                await self.bot.edit_message(msg, embed=em)
                                await asyncio.sleep(4)
                                await self.bot.delete_message(msg)
                                return
                            elif rep.content.isdigit():
                                totalqte = int(rep.content) * item["qte"]
                                prix = item["value"] * int(rep.content)
                                if cash.enough_credits(user, prix):
                                    if self.add_item(user, id=item["id"], type=item["type"], name=item["name"], qte=totalqte):
                                        cash.remove_credits(user, prix, "Achat Cobalt › {}".format(item["id"]), ["cobalt"])
                                        em = discord.Embed(description="**Merci pour votre achat.** Le contenu a été déplacé dans votre inventaire.",
                                                           color=0x00aa5e)
                                        em.set_author(name="Achat — {} [{}]".format(item["name"], itemid),
                                                      icon_url=user.avatar_url)
                                        await self.bot.edit_message(msg, embed=em)
                                        return
                                    else:
                                        em = discord.Embed(description="**Echec de la transaction** — Je n'ai pas pu transférer l'objet dans votre inventaire :(",
                                                          color=0xa90000)
                                        em.set_author(name="Achat — {}".format(item["name"]),
                                                      icon_url=user.avatar_url)
                                        await self.bot.edit_message(msg, embed=em)
                                        return
                                else:
                                    em = discord.Embed(description="**Solde insuffisant** — Essayez une plus faible quantité ou annulez la transaction en tapant \"stop\".",
                                                       color=0x0047AB)
                                    em.set_author(name="Achat — {}".format(item["name"]),
                                                  icon_url=user.avatar_url)
                                    await self.bot.edit_message(msg, embed=em)
                                    await asyncio.sleep(4)
                                    await self.bot.delete_message(msg)
                            else:
                                em = discord.Embed(description="**Quantité non reconnue** — Entrez la quantité désirée en chiffres ou annulez la transaction en tapant \"stop\".",
                                                   color=0x0047AB)
                                em.set_author(name="Achat — {}".format(item["name"]),
                                              icon_url=user.avatar_url)
                                await self.bot.edit_message(msg, embed=em)
                                await asyncio.sleep(4)
                                await self.bot.delete_message(msg)
                    else:
                        totalqte = qte * item["qte"]
                        prix = item["value"] * qte
                        if cash.enough_credits(user, prix):
                            if self.add_item(user, id=item["id"], type=item["type"], name=item["name"], qte=totalqte):
                                cash.remove_credits(user, prix, "Achat Cobalt › {}".format(item["id"]), ["cobalt"])
                                em = discord.Embed(description="**Merci pour votre achat.** Le contenu a été déplacé dans votre inventaire.",
                                                   color=0x00aa5e)
                                em.set_author(name="Achat — {} [{}]".format(item["name"], itemid),
                                              icon_url=user.avatar_url)
                                await self.bot.send_message(channel, embed=em)
                                return
                            else:
                                em = discord.Embed(description="**Echec de la transaction** — Je n'ai pas pu transférer l'objet dans votre inventaire :(",
                                                   color=0xa90000)
                                em.set_author(name="Achat — {}".format(item["name"]),
                                              icon_url=user.avatar_url)
                                await self.bot.send_message(channel, embed=em)
                                return
                        else:
                            em = discord.Embed(description="**Solde insuffisant** — Essayez une plus faible quantité.",
                                               color=0x0047AB)
                            em.set_author(name="Achat — {}".format(item["name"]),
                                          icon_url=user.avatar_url)
                            notif = await self.bot.send_message(channel, embed=em)
                            await asyncio.sleep(4)
                            await self.bot.delete_message(notif)
                else:
                    await self.bot.send_message(channel, "**Achat impossible** — Vous avez besoin d'un compte *Cash* valide.")
            else:
                await self.bot.send_message(channel, "**Banni·e** — Vous ne pouvez pas acheter d'items.")
        else:
            await self.bot.send_message(channel, "**Achat impossible** — L'item visé est unique et ne peut être acheté.")

    async def disp_astuce(self, comcontext: str = None, channel: discord.Channel = None):
        comcontext = random.choice(["buy_from_reaction", "fast_use", "partage", "sellall", "use_cumul", "mine_despawn",
                                    "mine_val", "calc_freq", "fast_buy"])
        title = "Astuces — "
        if comcontext == "buy_from_reaction":
            title += "Acheter depuis l'affichage de l'item"
            desc = "Saviez-vous qu'on peut parfois directement acheter un item en cliquant sur la réaction \🛒 se " \
                   "trouvant en dessous de l'affichage des détails ?"
        elif comcontext == "fast_use":
            title +="Utiliser un item plus rapidement"
            desc = "Il est possible de rentrer l'identifiant unique de l'item après `.use` pour utiliser l'item visé " \
                   "directement ! On retrouve cet identifiant entre crochets dans le titre de l'affichage de l'item."
        elif comcontext == "partage":
            title +="Partager rapidement un item"
            desc = "Saviez-vous qu'il est possible de partager un item sur n'importe quel salon en utilisant la balise" \
                   " fournie en bas de l'affichage de l'item ? Il se trouve toujours sous cette forme : `!Y$` avec Y l'identifiant de l'item."
        elif comcontext == "sellall":
            title +="Vendre tout ses minerais d'un coup"
            desc = "Il est en effet possible de faire `;shop sellall` ! Un écran de confirmation vous affichera la " \
                   "valeur totale de votre stock et vous permettra de tout vendre d'un coup !"
        elif comcontext == "use_cumul":
            title +="Cumul des effets à l'utilisation"
            desc = "Lorsque vous activez plusieurs fois le même item (par exemple, vous activez 3 détecteurs à la " \
                   "suite) ne vous inquiétez pas, ils ne sont pas perdus ! A chaque utilisation vous en utiliserez " \
                   "qu'un seul, même si plusieurs sont activés à la fois !"
        elif comcontext == "mine_despawn":
            title +="Disparition des minerais"
            desc = "Saviez-vous que les minerais, s'ils ne sont pas minés, disparaissent au bout de 120s ? " \
                   "Si c'est le cas, un autre apparaîtra peu de temps après donc restez à l'affut, il risque de " \
                   "revenir vite et parfois même en plus grande quantité !"
        elif comcontext == "mine_val":
            title += "Fluctuation de la valeur des minerais"
            desc = "Attention, la valeur des minerais peuvent fluctuer entre chaque mise à jour ! Restez à l'affût des " \
                   "changements pour éviter que votre stock perde en valeur après une MAJ !"
        elif comcontext == "calc_freq":
            title += "Calcul de la fréquence d'apparition"
            desc = "Saviez-vous que la fréquence d'apparition est calculée en fonction de l'activité sur le serveur ? " \
                   "Un serveur mort ne fera probablement jamais apparaître d'item !"
        elif comcontext == "fast_buy":
            title += "Acheter/vendre rapidement sur la boutique"
            desc = "Il est possible, plutôt que rentrer `buy` ou `sell` après la commande `;shop` de rentrer directement " \
                   "l'identifiant d'un minerai pour le vendre ou l'identifiant d'un équipement pour l'acheter !"
        em = discord.Embed(title=title, description=desc, color=0xf7f7f7)
        if not channel:
            msg = await self.bot.say(embed=em)
        else:
            msg = await self.bot.send_message(channel, embed=em)

# -----------------------------------------------------------------------------------------

    @commands.command(pass_context=True, aliases=["inv"], no_pm=True)
    async def sac(self, ctx):
        """Consulter son inventaire Cobalt"""
        cash = self.cash_api()
        cur = cash.get_currency(ctx.message.server)
        if not cash:
            await self.bot.say("**Erreur** — Impossible de contacter le module *Cash*.")
            return
        if not await cash.login(ctx.message.author):
            await self.bot.say("**Impossible** — Vous devez avoir un compte *Cash* valide.")
            return

        mtxt = random.choice(["Il n'y a rien à voir ici.", "Vide.", "RAS mon capitaine.", "C'est vide."])
        mequip = random.choice(["Aucun équipement", "Vous n'avez rien.", "Aucune possession."])
        utxt = random.choice(["Aucun objet unique.", "Vide.", "Pas d'objets uniques", "Rien à afficher."])
        data = self.get_user(ctx.message.author)
        if not data:
            "**Banni·e** — Vous ne pouvez pas consulter votre inventaire."
            return

        val = 0
        for m in data["minerais"]:
            unival = self.get_item(m)["value"]
            totm = unival * data["minerais"][m]["qte"]
            val += totm
        desc = "**Votre énergie** — {}\⚡ (max. {})\n".format(data["energie"], data["max_energie"])
        if data["status"]:
            desc += "**Items actifs** — {}\n".format(", ".join([self.get_item(i)["name"].lower() for i in data["status"]]))
        desc += "**Solde Cash** — {}\n".format(cur.tformat(cash.get_account(ctx.message.author).solde))
        desc += "**Valeur estimée du stock** — {}".format(cur.tformat(val))
        em = discord.Embed(description= desc, color=0x0047AB)
        if data["items"]:
            mequip = ""
            items = data["items"]
            for item in items:
                mequip += "• {}x **{}** — *{}*\n".format(items[item]["qte"], items[item]["name"],
                                                       self.get_item(item)["desc"])
        em.add_field(name="⚒ Equipement", value=mequip, inline=False)

        nb = 0
        if data["minerais"]:
            mtxt = ""
            minerais = data["minerais"]
            for item in minerais:
                nb += minerais[item]["qte"]
                mtxt += "• {}x **{}** — {}/unité\n".format(minerais[item]["qte"], minerais[item]["name"],
                                                     cur.sformat(self.get_item(item)["value"]))
        em.add_field(name="📦 Minerais ({}/{})".format(nb, data["max_capacite"]), value=mtxt, inline=False)

        if data["uniques"]:
            utxt = ""
            uniques = data["uniques"]
            for item in uniques:
                utxt += "• {}x **{}**\n".format(uniques[item]["qte"], uniques[item]["name"])
            em.add_field(name="🔑 Objets uniques", value=utxt)
        em.set_author(name="Votre inventaire", icon_url=ctx.message.author.avatar_url)
        await self.bot.say(embed=em)

    @commands.command(pass_context=True, no_pm=True)
    async def shop(self, ctx, item_action: str = None, qte: int = None):
        """Vendre ses minerais et acheter de l'équipement

        Pour aller plus vite, vous pouvez taper l'identifiant de l'item à vendre ou acheter"""
        stop = False
        cash = self.cash_api()
        cur = cash.get_currency(ctx.message.server)
        def check(reaction, user):
            return not user.bot
        user = self.get_user(ctx.message.author)
        if not user:
            "**Banni·e** — Vous ne pouvez pas consulter votre inventaire."
            return

        if not cash:
            await self.bot.say("**Erreur** — Impossible de contacter le module *Cash*.")
            return
        if not await cash.login(ctx.message.author):
            await self.bot.say("**Impossible** — Vous devez avoir un compte *Cash* valide.")
            return

        if not item_action:
            em = discord.Embed(title="Boutique » Aide", description="__**Actions que vous pouvez réaliser**__\n"
                                                                    "• Acheter des équipements = `;shop buy` / `;shop achat`\n"
                                                                    "• Vendre des ressources = `;shop sell` / `;shop vendre`\n"
                                                                    "• Vendre toutes vos ressources = `;shop sellall` / `;shop vendretout`\n"
                                                                    "• Acheter/Vendre directement un item = `;shop <item_id> <qté>`", color=0x0047AB)
            await self.bot.say(embed=em)
            return

        allitems = []
        for c in self.items:
            if c == "MINERAI" or c == "ITEM":
                for i in self.items[c]:
                    allitems.append(i)

        if item_action.lower() in ["buy", "achat"]:
            while not stop:
                txt = ""
                n = 1
                items = []
                for item in self.items["ITEM"]:
                    obj = self.items["ITEM"][item]
                    txt += "{} — **{}** › **{}**{}/{}\n".format(n, obj["name"], obj["value"], cur.symbole,
                                                              "unité" if obj["qte"] == 1 else "lot de " + str(obj["qte"]))
                    items.append([n, item])
                    n += 1
                em = discord.Embed(description=txt, color=0x0047AB)
                em.set_author(name="Boutique » Achat", icon_url=ctx.message.author.avatar_url)
                em.set_footer(text="» Tapez le numéro de l'item désiré | \"Quitter\" pour quitter")
                msg = await self.bot.say(embed=em)
                rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                      author=ctx.message.author,
                                                      timeout=20)
                if rep is None or rep.content.lower() in ["q", "stop", "quitter"]:
                    await self.bot.delete_message(msg)
                    return
                elif rep.content.lower() in ["r", "retour"]:
                    await self.bot.delete_message(msg)
                    stop = True
                    continue
                elif rep.content in [str(i[0]) for i in items]:
                    await self.bot.delete_message(msg)
                    for i in items:
                        if i[0] == int(rep.content):
                            await self.buy_item(ctx.message.channel, ctx.message.author, i[1])
                            if random.randint(1, 5) == 1:
                                await self.disp_astuce()
                    continue
                else:
                    await self.bot.say("**Erreur** — Il semblerait que le nombre soit incorrect. Réessayez.")
                    await self.bot.delete_message(msg)
        elif item_action.lower() in ["sell", "vendre"]:
            while not stop:
                minerais = user["minerais"]
                txt = ""
                for m in minerais:
                    unival = self.get_item(m)["value"]
                    totm = unival * minerais[m]["qte"]
                    txt += "{}x **{}** — {}{}/unité 》 **{}**\n".format(minerais[m]["qte"], minerais[m]["name"], cur.sformat(unival),
                                                                       totm)
                em = discord.Embed(description=txt, color=0x0047AB)
                em.set_footer(
                    text="» Tapez le nom de la ressource à vendre | \"Quitter\" pour quitter")
                em.set_author(name="Boutique » Vente", icon_url=ctx.message.author.avatar_url)
                msg = await self.bot.say(embed=em)
                rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                      author=ctx.message.author,
                                                      timeout=20)
                if rep is None or rep.content.lower() in ["q", "stop", "quitter"]:
                    await self.bot.delete_message(msg)
                    return
                if rep.content.lower() in minerais:
                    await self.bot.delete_message(msg)
                    mrep = rep.content.lower()
                    mine = minerais[rep.content.lower()]
                    em = discord.Embed(description="**Nombre d'unités possédées:** {}\n» Combien désirez-vous en vendre ?"
                                                   "".format(mine["qte"]),
                                       color=0x0047AB)
                    em.set_author(name="Boutique » Vente » {}".format(rep.content.title()),
                                  icon_url=ctx.message.author.avatar_url)
                    msg = await self.bot.say(embed=em)
                    rep = await self.bot.wait_for_message(channel=msg.channel, author=ctx.message.author, timeout=20)
                    if rep is None or rep.content.lower() in ["stop", "quitter", "q", "retour", "0"]:
                        em = discord.Embed(description="**Annulation de la transaction**",
                                           color=0xa90000)
                        em.set_author(name="Boutique » Vente » {}".format(mrep),
                                      icon_url=ctx.message.author.avatar_url)
                        await self.bot.edit_message(msg, embed=em)
                        await asyncio.sleep(4)
                        await self.bot.delete_message(msg)
                        continue
                    elif rep.content.isdigit():
                        qte = int(rep.content)
                        if qte <= mine["qte"]:
                            val = self.get_item(mrep)["value"] * qte
                            self.del_item(ctx.message.author, mrep, qte)
                            self.save()
                            cash.add_credits(ctx.message.author, val, "Vente Cobalt › {}".format(mrep), ["cobalt", "noreset"])
                            em.description = "Vente réalisée ! **{}** ont été transférés sur votre compte.".format(cur.sformat(val))
                            await self.bot.edit_message(msg, embed=em)
                            if random.randint(1, 5) == 1:
                                await self.disp_astuce()
                            continue
                        else:
                            em.description = "**Impossible** — Vous n'avez pas une telle quantité dans votre inventaire !"
                            await self.bot.edit_message(msg, embed=em)
                            continue
                    else:
                        em = discord.Embed(description="**Quantité non reconnue** — Entrez la quantité désirée en chiffres ou annulez la transaction en tapant \"stop\".",
                                           color=0x0047AB)
                        em.set_author(name="Boutique » Vente » {}".format(mrep),
                                      icon_url=ctx.message.author.avatar_url)
                        await self.bot.edit_message(msg, embed=em)
                        await asyncio.sleep(4)
                        await self.bot.delete_message(msg)
                else:
                    await self.bot.say("**Minerai inconnu** — Vous n'avez pas de ce minerai dans votre inventaire.")
                    await self.bot.delete_message(msg)
                    continue
        elif item_action.lower() in ["sellall", "vendretout"]:
            minerais = user["minerais"]
            txt = ""
            val = 0
            for m in minerais:
                unival = self.get_item(m)["value"]
                totm = unival * minerais[m]["qte"]
                txt += "{}x **{}** — {}/unité 》 **{}**\n".format(minerais[m]["qte"], minerais[m]["name"], cur.tformat(unival), cur.sformat(totm))
                val += totm
            txt = "\nTotal de la vente ⟫ **{}**".format(cur.tformat(val))
            em = discord.Embed(description=txt, color=0x0047AB)
            em.set_author(name="Boutique » Vente (Tout vendre)", icon_url=ctx.message.author.avatar_url)
            em.set_footer(text="» Êtes-vous certain de tout vendre ?")
            msg = await self.bot.say(embed=em)
            await asyncio.sleep(0.1)
            await self.bot.add_reaction(msg, "✅")
            await self.bot.add_reaction(msg, "❎")
            rep = await self.bot.wait_for_reaction(["✅", "❎"], message=msg, timeout=20, check=check,
                                                   user=ctx.message.author)
            if rep is None or rep.reaction.emoji == "❎":
                await self.bot.delete_message(msg)
                await self.bot.say("**Transaction annulée** — Vos minerais n'ont pas été vendus.")
                return
            else:
                self.reset_user_type(ctx.message.author, "minerais")
                self.save()
                cash.add_credits(ctx.message.author, val, "Vente Cobalt › SellAll", ["cobalt"])
                em.description = "Vente réalisée ! **{}** ont été transférés sur votre compte.".format(cur.tformat(val))
                em.set_footer(text="")
                await self.bot.edit_message(msg, embed=em)
                await self.bot.clear_reactions(msg)
                if random.randint(1, 5) == 1:
                    await self.disp_astuce()
        elif item_action.lower() in allitems:
            itemid = item_action.lower()
            item = self.get_item(itemid)
            if item["type"] is "MINERAI":
                mine = self.get_user(ctx.message.author)["minerais"]
                if itemid not in mine:
                    await self.bot.say("**Impossible** — Vous n'avez pas ce minerai sur vous.")
                    return
                mine = mine[itemid]
                if not qte:
                    em = discord.Embed(description="**Nombre d'unités possédées:** {}\n» Combien désirez-vous en vendre ?"
                                                   "".format(mine["qte"]),
                                       color=0x0047AB)
                    em.set_author(name="Boutique » Vente » {} [{}]".format(item["name"], itemid),
                                  icon_url=ctx.message.author.avatar_url)
                    msg = await self.bot.say(embed=em)
                    rep = await self.bot.wait_for_message(channel=msg.channel, author=ctx.message.author, timeout=20)
                    if rep is None or rep.content.lower() in ["stop", "quitter", "q", "retour", "0"]:
                        em = discord.Embed(description="**Annulation de la transaction**",
                                           color=0xa90000)
                        em.set_author(name="Boutique » Vente » {} [{}]".format(item["name"], itemid),
                                      icon_url=ctx.message.author.avatar_url)
                        await self.bot.edit_message(msg, embed=em)
                        await asyncio.sleep(4)
                        await self.bot.delete_message(msg)
                        return
                    elif rep.content.isdigit():
                        qte = int(rep.content)
                        if qte <= mine["qte"]:
                            val = self.get_item(itemid)["value"] * qte
                            if cash.add_credits(ctx.message.author, val,
                                                       "Vente Cobalt › {} [{}]".format(item["name"], itemid), ["cobalt", "noreset"]):
                                self.del_item(ctx.message.author, itemid, qte)
                                self.save()
                                em.description = "Vente réalisée ! **{}** ont été transférés sur votre compte.".format(cur.tformat(val))
                                await self.bot.edit_message(msg, embed=em)
                                if random.randint(1, 5) == 1:
                                    await self.disp_astuce()
                                return
                            else:
                                em.description = "**Erreur** — Il semblerait que la connexion à Cash ait été perdue.\n" \
                                                 "Ceci est un bug connu, contactez Acrown#4424 avant de retenter la vente."
                                await self.bot.edit_message(msg, embed=em)
                                return
                        else:
                            em.description = "**Impossible** — Vous n'avez pas une telle quantité dans votre inventaire !"
                            await self.bot.edit_message(msg, embed=em)
                            return
                    else:
                        em = discord.Embed(description="**Quantité non reconnue** — Entrez la quantité désirée en chiffres ou annulez la transaction en tapant \"stop\".",
                                           color=0x0047AB)
                        em.set_author(name="Boutique » Vente » {} [{}]".format(item["name"], itemid),
                                      icon_url=ctx.message.author.avatar_url)
                        await self.bot.edit_message(msg, embed=em)
                        await asyncio.sleep(4)
                        await self.bot.delete_message(msg)
                else:
                    if qte <= mine["qte"]:
                        val = self.get_item(itemid)["value"] * qte
                        self.del_item(ctx.message.author, itemid, qte)
                        self.save()
                        cash.add_credits(ctx.message.author, val, "Vente Cobalt › {}".format(item["name"]),
                                                ["cobalt", "noreset"])
                        em = discord.Embed(description="Vente réalisée ! **{}** ont été transférés sur votre compte."
                                                       "".format(cur.tformat(val)),
                                           color=0x0047AB)
                        em.set_author(name="Boutique » Vente » {} [{}]".format(item["name"], itemid),
                                      icon_url=ctx.message.author.avatar_url)
                        msg = await self.bot.say(embed=em)
                        if random.randint(1, 5) == 1:
                            await self.disp_astuce()
                        return
                    else:
                        em = discord.Embed(description="Vous n'avez pas cette quantité dans votre inventaire.",
                                           color=0x0047AB)
                        em.set_author(name="Boutique » Vente » {} [{}]".format(item["name"], itemid),
                                      icon_url=ctx.message.author.avatar_url)
                        msg = await self.bot.say(embed=em)
                        return
            else:
                await self.buy_item(ctx.message.channel, ctx.message.author, itemid, qte)
                if random.randint(1, 5) == 1:
                    await self.disp_astuce()
        else:
            await self.bot.say("**Action inconnue**\n*buy* = Acheter des équipements\n*sell* = Vendre des ressources\n"
                               "*sellall* = Vendre toutes vos ressources (minerais)\n*<itemid> <qte>* = Acheter/Vendre directement l'item possédant cet id")

    @commands.command(pass_context=True, no_pm=True)
    async def refundall(self, ctx):
        """Rembourse tous les items achetés"""
        user = self.get_user(ctx.message.author)
        cash = self.cash_api()
        cur = cash.get_currency(ctx.message.server)
        if not user:
            "**Banni·e** — Vous ne pouvez pas consulter votre inventaire."
            return

        if not cash:
            await self.bot.say("**Erreur** — Impossible de contacter le module *Cash*.")
            return
        if not await cash.login(ctx.message.author):
            await self.bot.say("**Impossible** — Vous devez avoir un compte *Cash* valide.")
            return

        equip = user["items"]
        txt = ""
        val = 0
        for m in equip:
            unival = round(self.get_item(m)["value"] / self.get_item(m)["qte"], 2)
            totm = round(unival * equip[m]["qte"], 2)
            txt += "{}x **{}** — {}/unité 》 **{}**\n".format(equip[m]["qte"], equip[m]["name"], cur.tformat(unival), cur.sformat(totm))
            val += totm
        val = int(val)
        txt += "\nTotal du remboursement ⟫ **{}**".format(cur.tformat(val))
        em = discord.Embed(description=txt, color=0x0047AB)
        em.set_author(name="Boutique » Remboursement (Tout revendre)", icon_url=ctx.message.author.avatar_url)
        em.set_footer(text="» Êtes-vous certain de tout revendre ?")
        msg = await self.bot.say(embed=em)
        await asyncio.sleep(0.1)
        await self.bot.add_reaction(msg, "✅")
        await self.bot.add_reaction(msg, "❎")
        rep = await self.bot.wait_for_reaction(["✅", "❎"], message=msg, timeout=30, user=ctx.message.author)
        if rep is None or rep.reaction.emoji == "❎":
            await self.bot.delete_message(msg)
            await self.bot.say("**Transaction annulée** — Vos items n'ont pas été revendus.")
            return
        else:
            self.reset_user_type(ctx.message.author, "items")
            self.save()
            cash.add_credits(ctx.message.author, val, "Remboursement Cobalt", ["cobalt"])
            em.description = "Revente réalisée ! **{}** ont été transférés sur votre compte.".format(cur.sformat(val))
            em.set_footer(text="")
            await self.bot.edit_message(msg, embed=em)
            await self.bot.clear_reactions(msg)
            if random.randint(1, 5) == 1:
                await self.disp_astuce()


    @commands.command(pass_context=True, no_pm=True)
    async def journal(self, ctx):
        """Affiche les dernières action sur Cobalt de la session en cours"""
        journal = self.get_heartbeat(ctx.message.server)["journal"]
        txt = ""
        n = 1
        if journal:
            for e in journal[::-1]:
                txt += "• {} — *{}*\n".format(time.strftime("%d/%m/%Y %H:%M", time.localtime(e[0])), e[1])
                if len(txt) >= 1980 * n:
                    em = discord.Embed(title="Journal d'actions Cobalt", description=txt, color=0xf7f7f7)
                    em.set_footer(text="Page n°{}".format(n))
                    await self.bot.say(embed=em)
                    n += 1
                    txt = ""
            if txt:
                em = discord.Embed(title="Journal d'actions Cobalt", description=txt, color=0xf7f7f7)
                em.set_footer(text="Page n°{}".format(n))
                await self.bot.say(embed=em)
        else:
            em = discord.Embed(title="Journal d'actions Cobalt", description="Rien à afficher pour cette session.", color=0xf7f7f7)
            await self.bot.say(embed=em)

    @commands.command(pass_context=True, no_pm=True, aliases=["dex"])
    async def details(self, ctx, *recherche):
        """Rechercher un item de Cobalt"""
        if recherche:
            results = {}
            allitems = []
            for cat in self.items:
                allitems = allitems + [(self.items[cat][e]["id"], tuple(self.items[cat][e]["name"].split() + [self.items[cat][e]["id"]])) for e in self.items[cat]]
            for i in recherche:
                for r in allitems:
                    if i.lower() in r[1]:
                        if r[0] not in results:
                            results[r[0]] = 1
                        else:
                            results[r[0]] += 1
            if results:
                final_result = ""
                if len(results) > 1:
                    top = sorted(results.items(), key=lambda u: u[1], reverse=True)
                    results = []
                    txt = ""
                    n = 1
                    for i in top:
                        txt += "{}. **{}**\n".format(n, self.get_item(i[0])["name"])
                        results.append((n, i[0]))
                        n += 1
                    em = discord.Embed(title="Résultats", description=txt, color=0x0047AB)
                    em.set_footer(text="» Entrez le numéro de l'item recherché | \"Q\" pour Quitter")
                    msg = await self.bot.say(embed=em)
                    rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                          author=ctx.message.author,
                                                          timeout=20)
                    if rep is None or rep.content.lower() in ["q", "stop", "quitter"]:
                        await self.bot.delete_message(msg)
                        return
                    elif rep.content in [str(i[0]) for i in results]:
                        for i in results:
                            if i[0] == int(rep.content):
                                final_result = i[1]
                    else:
                        n = await self.bot.say("**Invalide** — Chiffre non reconnu, réessayez.")
                        await asyncio.sleep(2)
                        await self.bot.delete_message(n)
                        await self.bot.delete_message(msg)
                        return
                else:
                    final_result = list(results)[0]

                if final_result:
                    await self.display_item(ctx.message.channel, final_result, True)
                else:
                    await self.bot.say("**Introuvable** — Aucun résultat ne peut être affiché.")
            else:
                await self.bot.say("**Introuvable** — Aucun résultat ne peut être affiché.")
        else:
            await self.bot.say("**Aucun résultat** — Cette commande sert à rechercher un item parmi ceux disponibles.")

    @commands.command(pass_context=True, no_pm=True)
    async def boostinv(self, ctx, ritem: str = None):
        """Booster son inventaire"""
        data = self.get_user(ctx.message.author)

    @commands.command(pass_context=True, no_pm=True)
    async def use(self, ctx, ritem: str = None):
        """Permet d'utiliser un équipement

        Entrer l'ID de l'item à utiliser permet de l'utiliser directement"""
        data = self.get_user(ctx.message.author)
        saveritem = False
        if not data:
            "**Banni·e** — Vous ne pouvez pas consulter votre inventaire."
            return

        if data["items"]:
            while data["items"]:
                mequip = ""
                items = data["items"]
                if not saveritem:
                    if not ritem:
                        for item in items:
                            mequip += "• **{}** 》 *{}* (x{}) — *{}*\n".format(item, items[item]["name"], items[item]["qte"],
                                                                   self.get_item(item)["desc"])
                        em = discord.Embed(title="Vos équipements", description=mequip, color=0x0047AB)
                        em.set_footer(text="» Entrez l'identifiant de l'item que vous voulez utiliser | \"Q\" pour quitter")
                        msg = await self.bot.say(embed=em)
                        rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                              author=ctx.message.author,
                                                              timeout=20)
                        action = rep.content.lower() if rep else None
                    else:
                        msg = await self.bot.say("**Utiliser directement** 》 *{}*".format(ritem))
                        action = ritem.lower()
                        saveritem = True
                        ritem = None
                        await asyncio.sleep(0.5)
                    if action is None or action in ["q", "stop", "quitter"]:
                        await self.bot.delete_message(msg)
                        return
                    elif action in items:
                        cible = items[action]
                        if cible["qte"] >= 1:
                            if action == "detector":
                                await self.bot.delete_message(msg)
                                if len(data["status"]) < 3:
                                    data["status"].append("detector")
                                    self.del_item(ctx.message.author, "detector", 1)
                                    await self.bot.say("**Détecteur activé** — Vous recevrez une notification 10s avant l'apparition du prochain minerai !")
                                else:
                                    await self.bot.say("**Impossible** — Vous ne pouvez utiliser plus de 3 items actifs à la fois !")
                            elif action == "booster":
                                await self.bot.delete_message(msg)
                                if len(data["status"]) < 3:
                                    data["status"].append("booster")
                                    self.del_item(ctx.message.author, "booster", 1)
                                    await self.bot.say(
                                        "**Booster activé** — Vous recevrez plus de minerai lors de votre prochain minage !")
                                else:
                                    await self.bot.say("**Impossible** — Vous ne pouvez utiliser plus de 3 items actifs à la fois !")
                            elif action == "barrenrj":
                                await self.bot.delete_message(msg)
                                data["energie"] = data["max_energie"]
                                self.del_item(ctx.message.author, "barrenrj", 1)
                                self.save()
                                await self.bot.say("**Energie restaurée** — Vous avez désormais {}\⚡".format(data["energie"]))
                            elif action == "coeurnrj":
                                await self.bot.delete_message(msg)
                                data["max_energie"] += 10
                                data["energie"] = data["max_energie"]
                                self.del_item(ctx.message.author, "coeurnrj", 1)
                                self.save()
                                await self.bot.say("**Coeur consommé** — Vous pouvez désormais avoir jusqu'à {}\⚡ (Votre énergie a aussi été rechargée)".format(data["max_energie"]))
                            elif action == "poche":
                                await self.bot.delete_message(msg)
                                data["max_capacite"] += 20
                                self.del_item(ctx.message.author, "poche", 1)
                                self.save()
                                await self.bot.say("**Poche supplémentaire ajoutée** — Vous pouvez désormais avoir jusqu'à {} items".format(data["max_capacite"]))
                            else:
                                await self.bot.delete_message(msg)
                                await self.bot.say("**Erreur** — Item inconnu.")
                                return
                            if random.randint(1, 5) == 1:
                                await self.disp_astuce()
                        else:
                            await self.bot.say("**Quantité insufissante** — Vous n'avez pas cet item.")
                    else:
                        await self.bot.say("**Erreur** — Item inconnu ou non possédé.")
                        await self.bot.delete_message(msg)
                        continue
                else:
                    return
            await self.bot.say("**Vous n'avez plus aucun item à utiliser !** — Fermeture du menu")
            return
        else:
            await self.bot.say("**Vide** — Vous ne possédez aucun item consommable ou utilisable.")

    @commands.command(pass_context=True, hidden=True)
    async def pingcash(self):
        """Teste la connexion avec le module Cash"""
        cash = self.cash_api()
        try:
            if cash.ping():
                await self.bot.say("Pong du module **Cash** reçu")
            else:
                await self.bot.say("Pong non reçu")
        except:
            await self.bot.say("Pong non reçu.")

    # --------------------------------------------------------------------------------------------

    @commands.group(name="cobaltset", aliases=["cset"], pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def _cobaltset(self, ctx):
        """Parametres de Cobalt"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_cobaltset.command(pass_context=True)
    async def channels(self, ctx, *channels):
        """Modifier les channels qui peuvent faire apparaître des items"""
        sys = self.get_server(ctx.message.server)["SYS"]
        if not channels:
            txt = ""
            for chan in sys["channels"]:
                try:
                    channel = self.bot.get_channel(chan)
                    txt += "• {}\n".format(channel.mention)
                except:
                    txt += "• ~~{}~~ (supprimé)\n".format(chan)
                    sys["channels"].remove(chan)
                    self.save()
            if not txt:
                txt = "**Aucun channel** — Pour ajouter une liste de channels, faîtes `;cset channels` et " \
                      "mentionnez à la suite les channels désirés."
            em = discord.Embed(title="Channels où peuvent apparaître les items", description=txt)
            em.set_footer(text="Modifier la liste » '.cset channels` puis mentionnez les channels")
            await self.bot.say(embed=em)
        else:
            channels = ctx.message.channel_mentions
            liste = [c.id for c in channels]
            sys["channels"] = liste
            self.save()
            await self.bot.say("**Channels modifiés !**")

    @_cobaltset.command(pass_context=True)
    async def maxfreq(self, ctx, val: int):
        """Modifier la fréquence d'apparition des items

        Doit être supérieure ou égale à 100"""
        if val >= 50:
            self.get_server(ctx.message.server)["SYS"]["maxfreq"] = val
            self.save()
            await self.bot.say("**Fréquence d'apparition modifiée !**")
        else:
            await self.bot.say("**Erreur** — La fréquence doit être supérieure à 100")

    @_cobaltset.command(pass_context=True)
    async def resetcobalt(self, ctx):
        """Reset le heartbeat du module (en cas de bug)"""
        hb = self.get_heartbeat(ctx.message.server)
        hb["ack"] = 0
        hb["item"] = None
        hb["limit"] = random.randint(50, 300)
        await self.bot.say("**Reset sans redémarrage** — Effectué")

    @_cobaltset.command(pass_context=True)
    @checks.admin_or_permissions(administrator=True)
    async def ackset(self, ctx, val: int):
        """Modifier le ACK (compteur)

        Doit être supérieure ou égale à 0"""
        if val >= 0:
            self.get_heartbeat(ctx.message.server)["ack"] = val
            await self.bot.say("**ACK modifié !**")
        else:
            await self.bot.say("**Erreur** — La valeur doit être supérieure ou égale à 0")

    @_cobaltset.command(pass_context=True)
    @checks.admin_or_permissions(administrator=True)
    async def itemset(self, ctx, itemid: str):
        """Modifier le prochain item à apparaître"""
        if self.get_item(itemid.lower()):
            self.get_heartbeat(ctx.message.server)["item"] = itemid.lower()
            await self.bot.say("**Item modifié** — {} sera le prochain item à apparaître.".format(self.get_item(
                itemid.lower())["name"]))
        else:
            await self.bot.say("**Erreur** — La valeur doit être supérieure ou égale à 0")

    @_cobaltset.command(pass_context=True)
    @checks.admin_or_permissions(administrator=True)
    async def ban(self, ctx, user: discord.Member):
        """Empêche un membre de jouer au jeu ou rétablir son compte"""
        data = self.get_user(user)
        if data:
            self.ban_user(user)
            await self.bot.say("**Joueur banni** — {} ne pourra plus jouer à Cobalt.".format(user.mention))
        else:
            self.unban_user(user)
            await self.bot.say("**Joueur débanni** — {} peut de nouveau jouer à Cobalt.".format(user.mention))

    # --------------------------------------------------------------------------------------------

    def gen_minerai(self):
        items = self.items["MINERAI"]
        maxrare = max([items[i]["rare"] for i in items])
        maxrare += 1
        rl = []
        for i in items:
            for _ in range(maxrare - items[i]["rare"]):
                rl.append(i)
        return random.choice(rl)

    async def msg_heartbeat(self, message):
        if message.server:
            if not message.author.bot:
                regex = re.compile(r"!(\w+)\$", re.IGNORECASE | re.DOTALL).findall(message.content)
                if regex:
                    await self.display_item(message.channel, regex[0], True)

                hb = self.get_heartbeat(message.server)
                sys = self.get_server(message.server)["SYS"]
                if sys["channels"]: # On vérifie que le module est en état de fonctionnemment sur le serveur
                    hb["ack"] += 1
                    if hb["ack"] >= hb["limit"]:
                        try:
                            channel = self.bot.get_channel(random.choice(sys["channels"]))
                            if not hb["item"]:
                                itemid = self.gen_minerai()
                                hb["item"] = itemid
                                print("nouvel item généré")
                            else:
                                itemid = hb["item"]
                            hb["ack"] = 0
                            if await self.obtain_item(channel, itemid):
                                print("item obtenu")
                                hb["limit"] = random.randint(int(sys["maxfreq"] / 4), sys["maxfreq"])
                                hb["item"] = False
                            else:
                                print("item non-obtenu")
                                hb["limit"] = int(sys["maxfreq"] / 4) + random.randint(25, 50)
                        except Exception as e:
                            print(e)
                            pass

                    data = self.get_user(message.author)
                    if data:
                        chance = random.randint(0, 10)
                        if chance == 0:
                            if data["energie"] < int(data["max_energie"] / 2):
                                self.get_user(message.author)["energie"] += 1

    async def dynamic_react(self, reaction, user):
        if reaction.message.channel:
            message = reaction.message
            if not user.bot:
                if message.id in self.glob["buy_queue"]:
                    channel = message.channel
                    await self.buy_item(channel, user, self.glob["buy_queue"][message.id])

# --------------------------------------------------------------------------------------------


def check_folders():
    folders = ("data", "data/cobalt/")
    for folder in folders:
        if not os.path.exists(folder):
            print("Creating " + folder + " folder...")
            os.makedirs(folder)


def check_files():
    if not os.path.isfile("data/cobalt/data.json"):
        print("Creating empty data.json...")
        fileIO("data/cobalt/data.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Cobalt(bot)
    bot.add_listener(n.msg_heartbeat, 'on_message')
    bot.add_listener(n.dynamic_react, 'on_reaction_add')
    bot.add_cog(n)

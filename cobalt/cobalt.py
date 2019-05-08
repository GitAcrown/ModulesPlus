import discord
from discord.ext import commands
from .utils.dataIO import fileIO, dataIO
from .utils import checks
from __main__ import send_cmd_help, settings
import re
import random
import asyncio
from copy import deepcopy
import os

items_list = {
  "MINERAI":{
    "fer": {"id": "fer", "name": "Fer", "value": 5, "max": 13, "rare": 1, "energie": 1},
    "cuivre": {"id": "cuivre", "name": "Cuivre", "value": 8, "max": 12, "rare": 1, "energie": 1},
    "argent": {"id": "argent", "name": "Argent", "value": 20, "max": 10, "rare": 2, "energie": 3},
    "or": {"id": "or", "name": "Or", "value": 32, "max": 9, "rare": 2, "energie": 4},
    "platine": {"id": "platine", "name": "Platine", "value": 27, "max": 10, "rare": 2, "energie": 3},
    "rubis": {"id": "rubis", "name": "Rubis", "value": 68, "max": 7, "rare": 3, "energie": 8},
    "diamant": {"id": "diamant", "name": "Diamant", "value": 95, "max": 5, "rare": 3, "energie": 10}
  },
  "UNIQUE":{
    "gespace": {"id": "gespace", "name": "Gemme de l'Espace", "qte": 1},
    "gesprit": {"id": "gesprit", "name": "Gemme de l'Esprit", "qte": 1},
    "game": {"id": "game", "name": "Gemme de l'Âme", "qte": 1},
    "grealite": {"id": "grealite", "name": "Gemme de la Réalité", "qte": 1},
    "gtemps": {"id": "gtemps", "name": "Gemme du Temps", "qte": 1},
    "gpouvoir": {"id": "gpouvoir", "name": "Gemme du Pouvoir", "qte": 1}
  },
  "ITEM":{
    "detector": {"id": "detector", "name": "Détecteur de minerai", "value": 70, "qte": 1, "desc": "Permet de recevoir une notification 10s avant qu'une entité apparaisse"},
    "booster": {"id": "booster", "name": "Booster de pioche", "value": 100, "qte": 1, "desc": "Permet d'obtenir davantage d'unités lors du minage"},
    "barrenrj": {"id": "barrenrj", "name": "Barre énergétique", "value": 150, "qte": 3, "desc": "Recharge l'énergie au maximum (\\⚡)"},
    "coeurnrj": {"id":  "coeurnrj", "name":  "Coeur énergétique", "value": 1000, "qte": 1, "desc": "Augmente de manière permanente l'énergie maximale (\\⚡)"}
  }
}

class Cobalt:
    """Minez, récoltez, enrichissez-vous !"""

    def __init__(self, bot):
        self.bot = bot
        self.data = dataIO.load_json("data/cobalt/data.json")
        self.items = items_list
        self.glob = {"buy_queue": {}}
        self.heartbeat = {}
        try:
            self.pay = self.bot.get_cog("Pay").pay
        except:
            print("COBALT - Impossible de charger Pay")
            self.pay = None

    def save(self):
        fileIO("data/cobalt/data.json", "save", self.data)
        return True

    def get_heartbeat(self, server: discord.Server):
        if server.id not in self.heartbeat:
            self.heartbeat[server.id] = {"ack": 0,
                                         "limit": random.randint(50, 300),
                                         "item": None}
        return self.heartbeat[server.id]

    def get_server(self, server: discord.Server):
        if server.id not in self.data:
            self.data[server.id] = {"SYS": {"channels": [],
                                            "maxfreq": 300},
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
                             "status": [],
                             "ban": False}
            self.save()
        return data[user.id] if data[user.id]["ban"] is False else {}

    def add_item(self, user: discord.Member, **item):
        """Ajoute un item/équipement à un joueur"""
        data = self.get_user(user)
        try:
            if item["type"] == "MINERAI":
                inv = data["minerais"]
                if item["id"] in inv:
                    itemid = item["id"]
                    inv[itemid]["qte"] += item["qte"]
                else:
                    itemid = item["id"]
                    inv[itemid] = {"name": item["name"], "qte": item["qte"]}
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
        if item["type"] is "MINERAI":
            qte = random.randint(1, item["max"])
            phrase = random.choice(["**{0}** (x{1}) est apparu ! Cliquez sur `⛏` pour le miner !",
                                    "**{0}** (x{1}) vient d'apparaître ! Cliquez sur `⛏` pour le miner !",
                                    "{1} unité(s) de **{0}** ont été exposés par le vent ! Cliquez sur `⛏` pour le miner !",
                                    "**{0}** (x{1}) vient d'être découvert ! Minez-le avec `⛏` !"])
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
                                                          "et va bientôt apparaître !".format(item["name"], channel.name))
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
            await self.bot.add_reaction(notif, "⛏")
            await asyncio.sleep(0.1)
            rep = await self.bot.wait_for_reaction(["⛏"], message=notif, timeout=120, check=check)
            if rep is None:
                await self.bot.delete_message(notif)
                return False
            elif rep.reaction.emoji == "⛏":
                data = self.get_user(rep.user)
                if data["energie"] >= item["energie"]:
                    await self.bot.clear_reactions(notif)
                    foot = ""
                    if self.have_status(rep.user, "booster", True):
                        qte *= 2
                        foot = "Boosté = minerai x2"
                    p = random.choice(["**{0}** a été miné ! {1} en obtient {2} unité(s).",
                                                    "{1} obtient **{0}** (x{2}) !",
                                                    "Bien joué {1} ! Tu obtiens {2} unité(s) de **{0}**"])
                    em.description = p.format(item["name"], rep.user.mention, qte)
                    em.set_footer(text=foot)
                    await self.bot.edit_message(notif, embed=em)
                    data["energie"] -= item["energie"]
                    self.add_item(rep.user, id=item["id"], type=item["type"], name=item["name"], qte=qte)
                    return True
                else:
                    await self.bot.clear_reactions(notif)
                    em.description = "{} a tenté de miner **{}** mais n'avait pas assez d'énergie ! " \
                                     "Il a détruit le minerai.".format(rep.user, item["name"])
                    em.set_footer(text="")
                    await self.bot.edit_message(notif, embed=em)
                    return True
            else:
                print("**Erreur COBALT** 01 - Le mauvais emoji a été utilisé alors qu'il n'est pas censé être détecté.")
        elif item == "UNIQUE":
            qte = random.randint(1, item["max"])
            phrase = random.choice(["**{0}** est apparu ! Cliquez sur `🖐` pour le ramasser !",
                                    "**{0}** vient d'apparaître ! Cliquez sur `🖐` pour ramasser l'item !"])
            em = discord.Embed(description=phrase.format(item["name"], qte), color=0x0047AB)
            if "imageurl" in item:
                em.set_thumbnail(url=item["imageurl"])

            notif = await self.bot.send_message(channel, embed=em)
            def check(reaction, user):
                if not user.bot:
                    return True if self.get_user(user) else False
                return False
            await self.bot.add_reaction(notif, "🖐")
            await asyncio.sleep(0.1)
            rep = await self.bot.wait_for_reaction(["🖐"], message=notif, timeout=120, check=check)
            if rep is None:
                await self.bot.delete_message(notif)
                return False
            elif rep.reaction.emoji == "🖐":
                await self.bot.clear_reactions(notif)
                p = random.choice(["{0} a ramassé **{1}** !", "{0} obtient **{1}** !"])
                em.description = p.format(rep.user.mention, item["name"])
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
        if "desc" in item:
            txt += "*{}*\n\n".format(item["desc"])
        txt +=  "• **Type**: {}\n".format(typetxt)
        if "value" in item:
            txt += "• **Valeur**: {}{}".format(item["value"], "g/unité" if item["type"] != "ITEM" else "g")
        if "qte" in item:
            if item["qte"] > 1:
                txt += " (lot de {})".format(item["qte"])
        txt += "\n"
        if "rare" in item:
            txt += "• **Niveau de rareté**: {}\n".format(item["rare"])
        if "energie" in item:
            txt += "• **Energie nécessaire**: {}\⚡\n".format(item["energie"] if item["energie"] > 0 else "∞")
        em = discord.Embed(title=typesymbol + " " + item["name"], description=txt, color=0x0047AB)
        foot = "Partager - !{}$".format(itemid)
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

    async def buy_item(self, channel: discord.Channel, user: discord.Member, itemid):
        item = self.get_item(itemid)
        data = self.get_user(user)
        if item["type"] != "UNIQUE": # On ne peut pas acheter un item unique !
            if data:
                if not self.pay:
                    await self.bot.send_message(channel, "**Erreur** — Impossible de contacter le module *Pay*")
                    return
                if await self.pay.account_dial(user):
                    while True:
                        txt = ""
                        if "desc" in item:
                            txt = "*{}*\n".format(item["desc"])
                        if "qte" in item:
                            if item["qte"] > 1:
                                txt += "Vendu par __lot de {}__, chaque lot coûtant **{}g**".format(item["qte"], item["value"])
                        else:
                            txt += "Chaque unité coûte **{}g**".format(item["value"])
                        em = discord.Embed(title="Achat — {}".format(item["name"]), description=txt, color=0x0047AB)
                        if "imageurl" in item:
                            em.set_thumbnail(url=item["imageurl"])
                        em.set_footer(text="» Combien en voulez-vous ? | \"Stop\" pour annuler")
                        msg = await self.bot.send_message(channel, embed=em)
                        rep = await self.bot.wait_for_message(channel=msg.channel, author=user, timeout=20)
                        if rep is None or rep.content.lower() in ["stop", "quitter", "q"]:
                            em = discord.Embed(title="Achat — {}".format(item["name"]),
                                               description="**Annulation de la transaction**",
                                               color=0xa90000)
                            await self.bot.edit_message(msg, embed=em)
                            await asyncio.sleep(4)
                            await self.bot.delete_message(msg)
                            return
                        elif rep.content.isdigit():
                            qte = int(rep.content)
                            prix = item["value"] * qte
                            if self.pay.enough_credits(user, prix):
                                if self.add_item(user, id=item["id"], type=item["type"], name=item["name"], qte=qte):
                                    self.pay.remove_credits(user, prix, "Achat Cobalt › {}".format(item["id"]))
                                    em = discord.Embed(title="Achat — {}".format(item["name"]),
                                                       description="**Merci pour votre achat.** Le contenu à été déplacé dans votre inventaire.",
                                                       color=0x00aa5e)
                                    await self.bot.edit_message(msg, embed=em)
                                    return
                                else:
                                    em = discord.Embed(title="Achat — {}".format(item["name"]),
                                                      description="**Echec de la transaction** — Je n'ai pas pu transférer l'objet dans votre inventaire :(",
                                                      color=0xa90000)
                                    await self.bot.edit_message(msg, embed=em)
                                    return
                            else:
                                em = discord.Embed(title="Achat — {}".format(item["name"]),
                                                   description="**Solde insuffisant** — Essayez une plus faible quantité ou annulez la transaction en tapant \"stop\".",
                                                   color=0x0047AB)
                                await self.bot.edit_message(msg, embed=em)
                                await asyncio.sleep(4)
                                await self.bot.delete_message(msg)
                        else:
                            em = discord.Embed(title="Achat — {}".format(item["name"]),
                                               description="**Quantité non reconnue** — Entrez la quantité désirée en chiffres ou annulez la transaction en tapant \"stop\".",
                                               color=0x0047AB)
                            await self.bot.edit_message(msg, embed=em)
                            await asyncio.sleep(4)
                            await self.bot.delete_message(msg)
                else:
                    await self.bot.send_message(channel, "**Achat impossible** — Vous avez besoin d'un compte *Pay* valide.")
            else:
                await self.bot.send_message(channel, "**Banni·e** — Vous ne pouvez pas acheter d'items.")
        else:
            await self.bot.send_message(channel, "**Achat impossible** — L'item visé est unique et ne peut être acheté.")

    async def disp_astuce(self, comcontext: str = None, channel: discord.Channel = None):
        comcontext = random.choice(["buy_from_reaction", "fast_use", "partage", "sellall", "use_cumul", "mine_despawn"])
        title = "Astuces — "
        if comcontext == "buy_from_reaction":
            title += "Acheter depuis l'affichage de l'item"
            desc = "Saviez-vous qu'on peut parfois directement acheter un item en cliquant sur la réaction \🛒 se " \
                   "trouvant en dessous de l'affichage des détails ?"
        elif comcontext == "fast_use":
            title="Utiliser un item plus rapidement"
            desc = "Il est possible de rentrer l'identifiant unique de l'item après `.use` pour utiliser l'item visé " \
                   "directement ! On retrouve cet identifiant entre les caractères `!` et `§` dans le lien de partage."
        elif comcontext == "partage":
            title="Partager rapidement un item"
            desc = "Saviez-vous qu'il est possible de partager un item sur n'importe quel salon en utilisant la balise" \
                   " fournie en bas de l'affichage de l'item ? Il se trouve toujours sous cette forme : `!Y$` avec Y l'identifiant de l'item."
        elif comcontext == "sellall":
            title="Vendre tout ses minerais d'un coup"
            desc = "Il est en effet possible de faire `.shop sellall` ! Un écran de confirmation vous affichera la " \
                   "valeur totale de votre stock et vous permettra de tout vendre d'un coup !"
        elif comcontext == "use_cumul":
            title="Cumul des effets à l'utilisation"
            desc = "Lorsque vous activez plusieurs fois le même item (par exemple, vous activez 3 détecteurs à la " \
                   "suite) ne vous inquiétez pas, ils ne sont pas perdus ! A chaque utilisation vous en utiliserez " \
                   "qu'un seul, même si plusieurs sont activés à la fois !"
        elif comcontext == "mine_despawn":
            title="Disparition des minerais"
            desc = "Saviez-vous que les minerais, s'ils ne sont pas minés, disparaissent au bout de 120s ? " \
                   "Si c'est le cas, un autre apparaîtra peu de temps après donc restez à l'affut, il risque de revenir vite !"
        em = discord.Embed(title=title, description=desc, color=0xf7f7f7)
        if not channel:
            msg = await self.bot.say(embed=em)
        else:
            msg = await self.bot.send_message(channel, embed=em)
        await asyncio.sleep(5)
        await self.bot.delete_message(msg)

# -----------------------------------------------------------------------------------------

    @commands.command(pass_context=True, aliases=["inv"], no_pm=True)
    async def sac(self, ctx):
        """Consulter son inventaire Cobalt"""
        if not self.pay:
            await self.bot.say("**Erreur** — Impossible de contacter le module *Pay*.")
            return
        if not await self.pay.account_dial(ctx.message.author):
            await self.bot.say("**Impossible** — Vous devez avoir un compte *Pay* valide.")
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
        desc += "**Solde Pay** — {}g\n".format(self.pay.get_account(ctx.message.author, True).solde)
        desc += "**Valeur estimée du stock** — {} golds".format(val)
        em = discord.Embed(title="Votre inventaire", description= desc, color=0x0047AB)
        if data["items"]:
            mequip = ""
            items = data["items"]
            for item in items:
                mequip += "• {}x **{}** — *{}*\n".format(items[item]["qte"], items[item]["name"],
                                                       self.get_item(item)["desc"])
        em.add_field(name="⚒ Equipement", value=mequip)

        if data["minerais"]:
            mtxt = ""
            minerais = data["minerais"]
            for item in minerais:
                mtxt += "• {}x **{}** — {}g/unité\n".format(minerais[item]["qte"], minerais[item]["name"],
                                                     self.get_item(item)["value"])
        em.add_field(name="📦 Minerais", value=mtxt)

        if data["uniques"]:
            utxt = ""
            uniques = data["uniques"]
            for item in uniques:
                utxt += "• {}x **{}**\n".format(uniques[item]["qte"], uniques[item]["name"])
            em.add_field(name="🔑 Objets uniques", value=utxt)
        await self.bot.say(embed=em)

    @commands.command(pass_context=True, no_pm=True)
    async def shop(self, ctx, action: str = None):
        """Vendre ses minerais et acheter de l'équipement

        Pour aller plus vite, vous pouvez taper 'sell' ou 'buy' à la suite de la commande pour y accéder directement"""
        stop = False
        def check(reaction, user):
            return not user.bot
        user = self.get_user(ctx.message.author)
        if not user:
            "**Banni·e** — Vous ne pouvez pas consulter votre inventaire."
            return

        if not self.pay:
            await self.bot.say("**Erreur** — Impossible de contacter le module *Pay*.")
            return
        if not await self.pay.account_dial(ctx.message.author):
            await self.bot.say("**Impossible** — Vous devez avoir un compte *Pay* valide.")
            return

        if not action:
            em = discord.Embed(title="Boutique » Aide", description="__**Actions que vous pouvez réaliser**__\n"
                                                                    "• Acheter des équipements = `.shop buy` / `.shop achat`\n"
                                                                    "• Vendre des ressources = `.shop sell` / `.shop vendre`\n"
                                                                    "• Vendre toutes vos ressources = `.shop sellall` / `.shop vendretout`", color=0x0047AB)
            await self.bot.say(embed=em)
            return

        if action.lower() in ["buy", "achat"]:
            while not stop:
                txt = ""
                n = 1
                items = []
                for item in self.items["ITEM"]:
                    obj = self.items["ITEM"][item]
                    txt += "{}. **{}** › **{}**g/{}\n".format(n, obj["name"], obj["value"],
                                                              "unité" if obj["qte"] == 1 else "lot de " + str(obj["qte"]))
                    items.append([n, item])
                    n += 1
                em = discord.Embed(title="Boutique » Achat", description=txt, color=0x0047AB)
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
                    for i in items:
                        if i[0] == int(rep.content):
                            await self.display_item(ctx.message.channel, i[1], True, True)
                            await self.bot.delete_message(msg)
                            if random.randint(1, 3) == 1:
                                await self.disp_astuce()
                            continue
                    await self.bot.say("**Erreur** — Il semblerait que le nombre soit incorrect.")
                    await self.bot.delete_message(msg)
                    stop = True
                    continue
                else:
                    await self.bot.say("**Erreur** — Il semblerait que le nombre soit incorrect. Réessayez.")
                    await self.bot.delete_message(msg)
        elif action.lower() in ["sell", "vendre"]:
            while not stop:
                minerais = user["minerais"]
                txt = ""
                for m in minerais:
                    unival = self.get_item(m)["value"]
                    totm = unival * minerais[m]["qte"]
                    txt += "{}x **{}** — {}g/unité 》 **{}**g\n".format(minerais[m]["qte"], minerais[m]["name"], unival,
                                                                       totm)
                em = discord.Embed(title="Boutique » Vente", description=txt, color=0x0047AB)
                em.set_footer(
                    text="» Tapez le nom de la ressource à vendre | \"Quitter\" pour quitter")
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
                    em = discord.Embed(title="Boutique » Vente » {}".format(rep.content.title()),
                                       description="**Nombre d'unités possédées:** {}\n» Combien désirez-vous en vendre ?"
                                                   "".format(mine["qte"]),
                                       color=0x0047AB)
                    msg = await self.bot.say(embed=em)
                    rep = await self.bot.wait_for_message(channel=msg.channel, author=ctx.message.author, timeout=20)
                    if rep is None or rep.content.lower() in ["stop", "quitter", "q", "retour"]:
                        em = discord.Embed(title="Boutique » Vente » {}".format(mrep),
                                           description="**Annulation de la transaction**",
                                           color=0xa90000)
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
                            self.pay.add_credits(ctx.message.author, val, "Vente Cobalt › {}".format(mrep))
                            em.description = "Vente réalisée ! **{}**g ont été transférés sur votre compte.".format(val)
                            await self.bot.edit_message(msg, embed=em)
                            if random.randint(1, 3) == 1:
                                await self.disp_astuce()
                            continue
                        else:
                            em.description = "**Impossible** — Vous n'avez pas une telle quantité dans votre inventaire !"
                            await self.bot.edit_message(msg, embed=em)
                            continue
                    else:
                        em = discord.Embed(title="Boutique » Vente » {}".format(mrep),
                                           description="**Quantité non reconnue** — Entrez la quantité désirée en chiffres ou annulez la transaction en tapant \"stop\".",
                                           color=0x0047AB)
                        await self.bot.edit_message(msg, embed=em)
                        await asyncio.sleep(4)
                        await self.bot.delete_message(msg)
                else:
                    await self.bot.say("**Minerai inconnu** — Vous n'avez pas de ce minerai dans votre inventaire.")
                    await self.bot.delete_message(msg)
                    continue
        elif action.lower() in ["sellall", "vendretout"]:
            minerais = user["minerais"]
            txt = ""
            val = 0
            for m in minerais:
                unival = self.get_item(m)["value"]
                totm = unival * minerais[m]["qte"]
                txt += "{}x **{}** — {}g/unité 》 **{}**g\n".format(minerais[m]["qte"], minerais[m]["name"], unival, totm)
                val += totm
            txt = "\nTotal de la vente ⟫ **{}** golds".format(val)
            em = discord.Embed(title="Boutique » Vente (Tout vendre)", description=txt, color=0x0047AB)
            em.set_footer(text="» Êtes-vous certain de tout vendre ?")
            msg = await self.bot.say(embed=em)
            await self.bot.add_reaction(msg, "✅")
            await self.bot.add_reaction(msg, "❎")
            await asyncio.sleep(0.1)
            rep = await self.bot.wait_for_reaction(["✅", "❎"], message=msg, timeout=20, check=check,
                                                   user=ctx.message.author)
            if rep is None or rep.reaction.emoji == "❎":
                await self.bot.delete_message(msg)
                await self.bot.say("**Transaction annulée** — Vos minerais n'ont pas été vendus.")
                return
            else:
                self.reset_user_type(ctx.message.author, "minerais")
                self.save()
                self.pay.add_credits(ctx.message.author, val, "Vente Cobalt › SellAll")
                em.description = "Vente réalisée ! **{}**g ont été transférés sur votre compte.".format(val)
                em.set_footer(text="")
                await self.bot.edit_message(msg, embed=em)
                if random.randint(1, 3) == 1:
                    await self.disp_astuce()
        else:
            await self.bot.say("**Action inconnue**\n*buy* = Acheter des équipements\n*sell* = Vendre des ressources\n*sellall* = Vendre toutes vos ressources (minerais)")

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
    async def use(self, ctx, itemid: str = None):
        """Permet d'utiliser un équipement

        Entrer l'ID de l'item à utiliser permet de l'utiliser directement"""
        data = self.get_user(ctx.message.author)
        if not data:
            "**Banni·e** — Vous ne pouvez pas consulter votre inventaire."
            return

        if data["items"]:
            while data["items"]:
                mequip = ""
                items = data["items"]
                for item in items:
                    mequip += "`{}` **{}** (x{}) — *{}*\n".format(item, items[item]["name"], items[item]["qte"],
                                                           self.get_item(item)["desc"])
                em = discord.Embed(title="Vos équipements", description=mequip, color=0x0047AB)
                em.set_footer(text="» Entrez l'identifiant de l'item que vous voulez utiliser | \"Q\" pour quitter")
                msg = await self.bot.say(embed=em)
                rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                      author=ctx.message.author,
                                                      timeout=20)
                if rep is None or rep.content.lower() in ["q", "stop", "quitter"]:
                    await self.bot.delete_message(msg)
                    return
                elif rep.content.lower() in items:
                    cible = items[rep.content.lower()]
                    if cible["qte"] >= 1:
                        if rep.content.lower() == "detector":
                            await self.bot.delete_message(msg)
                            data["status"].append("detector")
                            self.del_item(ctx.message.author, "detector", 1)
                            await self.bot.say("**Détecteur activé** — Vous recevrez une notification 10s avant l'apparition du prochain minerai !")
                        elif rep.content.lower() == "booster":
                            await self.bot.delete_message(msg)
                            data["status"].append("booster")
                            self.del_item(ctx.message.author, "booster", 1)
                            await self.bot.say("**Booster activé** — Vous recevrez le double de minerai lors de votre prochain minage !")
                        elif rep.content.lower() == "barrenrj":
                            await self.bot.delete_message(msg)
                            data["energie"] = data["max_energie"]
                            self.del_item(ctx.message.author, "barrenrj", 1)
                            self.save()
                            await self.bot.say("**Energie restaurée** — Vous avez désormais {}\⚡".format(data["energie"]))
                        elif rep.content.lower() == "coeurnrj":
                            await self.bot.delete_message(msg)
                            data["max_energie"] += 10
                            self.del_item(ctx.message.author, "coeurnrj", 1)
                            self.save()
                            await self.bot.say("**Coeur consommé** — Vous pouvez désormais avoir jusqu'à {}\⚡".format(data["max_energie"]))
                        else:
                            await self.bot.delete_message(msg)
                            await self.bot.say("**Erreur** — Item inconnu.")
                            return
                        if random.randint(1,3) == 1:
                            await self.disp_astuce()
                    else:
                        await self.bot.say("**Quantité insufissante** — Vous n'avez pas cet item.")
                else:
                    await self.bot.say("**Erreur** — Item inconnu.")
                    await self.bot.delete_message(msg)
                    continue
            await self.bot.say("**Vous n'avez plus aucun item à utiliser !** — Fermeture du menu")
            return
        else:
            await self.bot.say("**Vide** — Vous ne possédez aucun item consommable ou utilisable.")

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
                txt = "**Aucun channel** — Pour ajouter une liste de channels, faîtes `.cset channels` et " \
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
        if val >= 100:
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
                            else:
                                itemid = hb["item"]
                            hb["ack"] = 0
                            if await self.obtain_item(channel, itemid):
                                hb["limit"] = random.randint(50, sys["maxfreq"])
                                hb["item"] = None
                            else:
                                hb["limit"] = random.randint(50, sys["maxfreq"] / 2)
                        except Exception as e:
                            print(e)
                            pass

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

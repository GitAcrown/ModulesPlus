import asyncio
import os
import random
import re
import time
from collections import namedtuple
from copy import deepcopy
from urllib import request

import aiohttp
import discord
from __main__ import send_cmd_help
from discord.ext import commands

from .utils import checks
from .utils.dataIO import fileIO, dataIO


class Echo:
    """Stickers et fonctionnalités dédiées aux salons écrits"""
    def __init__(self, bot):
        self.bot = bot
        self.data = dataIO.load_json("data/echo/data.json")
        self.sys = dataIO.load_json("data/echo/sys.json")
        self.cooldown = {}
        # BORDEL D'IMPORT
        if os.path.exists("data/stickers/stk.json"): # Ancien univ
            self.backup_univ = dataIO.load_json("data/stickers/stk.json")
        else:
            self.backup_univ = False
        if os.path.exists("data/systex/stk.json"): # EK
            self.backup_ek = dataIO.load_json("data/systex/stk.json")
        else:
            self.backup_ek = False
        self.defaut_quit = ["Au revoir {user.mention} !", "Bye bye {user.mention}.",
                            "{user.mention} s'est trompé de bouton.",
                            "{user.mention} a été suicidé de deux bans dans le dos.",
                            "{user.mention} a ragequit le serveur.",
                            "GAME OVER {user.mention}",
                            "A jamais {user.mention} !",
                            "Les meilleurs partent en premier, sauf {user.mention}...",
                            "{user.mention} est parti, un de moins !",
                            "{user.mention} s'envole vers d'autres cieux !",
                            "YOU DIED {user.mention}",
                            "De toute évidence {user.mention} ne faisait pas parti de l'élite.",
                            "{user.mention} a sauté d'un trottoir.",
                            "{user.mention} a roulé jusqu'en bas de la falaise.",
                            "{user.mention} est parti ouvrir son propre serveur...",
                            "{user.mention} n'était de toute évidence pas assez *gaucho* pour ce serveur.",
                            "{user.mention}... désolé c'est qui ce random ?",
                            "On m'annonce à l'oreillette que {user.mention} est parti.",
                            "C'est la fin pour {user.mention}...",
                            "{user.mention} a été jeté dans la fosse aux randoms.",
                            "{user.mention} est parti rejoindre Johnny...",
                            "{user.mention} ne supportait plus d'être l'*Omega* du serveur.",
                            "{user.mention} a paniqué une fois de plus.",
                            "{user.mention} s'est *enfin* barré !",
                            "Plus besoin de le bloquer, {user.mention} est parti !",
                            "Boop bip boup {user.mention} bip",
                            "{user.mention} a pris sa retraite.",
                            "{user.mention} a disparu dans des circonstances floues...",
                            "Non pas toi {user.mention} ! 😢",
                            "{user.mention} a quitté. Un de plus ou un de moins hein...",
                            "{user.mention} était de toute évidence trop underground pour ce serveur de normies.",
                            "{user.mention} est parti faire une manif'.",
                            "{user.mention} a quitté/20",
                            "Ce n'est qu'un *au revoir* {user.mention} !"]

    def save(self):
        fileIO("data/echo/data.json", "save", self.data)
        fileIO("data/echo/sys.json", "save", self.sys)
        return True

    def _set_server(self, server: discord.Server):
        if server.id not in self.data:
            self.data[server.id] = {}
            self.save()
        if server.id not in self.sys:
            perms = {"AJOUTER": "manage_messages",
                     "SUPPRIMER": "manage_messages",
                     "EDITER": "manage_messages",
                     "UTILISER": None}
            disp = {"IMAGE": "upload",
                    "AUDIO": "upload",
                    "VIDEO": "web"}
            dl = {"IMAGE": True,
                  "AUDIO": True,
                  "VIDEO": False}
            self.sys[server.id] = {"PERMISSIONS_STK": perms, "DISPLAY_STK": disp, "DOWNLOAD_STK": dl,
                                   "BLACKLIST": [], "CORRECT": None, "COOLDOWN": 3, "QUIT_MSG": self.defaut_quit,
                                   "QUIT": False}
            if not os.path.exists("data/echo/img/{}".format(server.id)):
                os.makedirs("data/echo/img/{}".format(server.id))
            self.save()
        if "QUIT_MSG" not in self.sys[server.id]:
            self.sys[server.id]["QUIT_MSG"] = self.defaut_quit
            self.sys[server.id]["QUIT"] = False
            self.save()
        return True

    def _obj_sticker(self, server: discord.Server, nom: str):
        """Renvoie l'objet Sticker() contenant toutes ses données"""
        self._set_server(server)
        for stk in self.data[server.id]:
            if nom == self.data[server.id][stk]["NOM"]:
                data = self.data[server.id][stk]
                output = re.compile(r"([A-z]+)(\d*)?", re.DOTALL | re.IGNORECASE).findall(nom)
                if output:
                    racine = output[0][0]
                    nb = output[0][1]
                else:
                    racine = nom
                    nb = ""
                if "giphy" in data["URL"] or "imgur" in data["URL"]:
                    ext = "gif"
                else:
                    fichnom = data["URL"].split("/")[-1]
                    ext = fichnom.split(".")[-1]
                typex = self.get_sticker_type(ext)
                Stats = namedtuple('Stats', ['compte', 'like', 'dislike'])
                if "NEED_REPAIR" not in data:
                    repair = False
                else:
                    repair = data["NEED_REPAIR"]
                stats = Stats(data["STATS"]["COMPTE"], data["STATS"]["LIKE"], data["STATS"]["DISLIKE"])
                Sticker = namedtuple('Sticker', ['id', 'nom', 'path', 'author', 'url', 'creation', 'stats', 'display',
                                                 'racine', 'place', 'type', 'approb', 'repair'])
                return Sticker(stk, data["NOM"], data["PATH"] if data["PATH"] else False,
                               data["AUTHOR"], data["URL"], data["CREATION"],
                               stats, data["DISPLAY"], racine, nb, typex, data["APPROB"], repair)
        return False

    def get_sticker(self, server: discord.Server, nom: str, w: bool = False, pass_approb: bool = False):
        self._set_server(server)
        for stk in self.data[server.id]:
            if nom == self.data[server.id][stk]["NOM"]:
                if self.data[server.id][stk]["APPROB"] or pass_approb:
                    if w:
                        return self.data[server.id][stk]
                    return self._obj_sticker(server, nom)
        else:
            return False

    def approb_list(self, server: discord.Server):
        self._set_server(server)
        liste = []
        for stk in self.data[server.id]:
            if self.data[server.id][stk]["APPROB"] is False:
                liste.append(self._obj_sticker(server, self.data[server.id][stk]["NOM"]))
        return liste

    def get_all_stickers(self, server: discord.Server, approuved: bool = False, type: str = None):
        self._set_server(server)
        all = []
        for s in self.data[server.id]:
            if approuved:
                if self.data[server.id][s]["APPROB"]:
                    if type:
                        all.append(self.data[server.id][s][type.upper()])
                    else:
                        all.append(self._obj_sticker(server, self.data[server.id][s]["NOM"]))
            else:
                if type:
                    all.append(self.data[server.id][s][type.upper()])
                else:
                    all.append(self._obj_sticker(server, self.data[server.id][s]["NOM"]))
        return all

    def add_sticker(self, nom: str, author: discord.Member, url: str, chemin: str = None, replace: bool = False):
        """Ajoute un sticker sur le serveur"""
        server = author.server
        self._set_server(server)
        if not self._obj_sticker(server, nom):
            clef = str(random.randint(100000, 999999))
            if clef in self.data[server.id]:
                return self.add_sticker(nom, author, url, chemin)
            stats = {"COMPTE": {},
                     "LIKE": [],
                     "DISLIKE": []}
            fichnom = url.split("/")[-1]
            ext = fichnom.split(".")[-1]
            self.data[server.id][clef] = {"NOM": nom,
                                          "PATH": chemin,
                                          "AUTHOR": author.id,
                                          "URL": url,
                                          "CREATION": time.time(),
                                          "STATS": stats,
                                          "DISPLAY": self.get_display(server, self.get_sticker_type(ext)),
                                          "APPROB": self.get_perms(author, "AJOUTER"),
                                          "NEED_REPAIR": False}
            self.save()
            return True if self.get_perms(author, "AJOUTER") else False
        if replace:
            clef = self.get_sticker(server, nom).id
            stats = {"COMPTE": {},
                     "LIKE": [],
                     "DISLIKE": []}
            fichnom = url.split("/")[-1]
            ext = fichnom.split(".")[-1]
            self.data[server.id][clef] = {"NOM": nom,
                                          "PATH": chemin,
                                          "AUTHOR": author.id,
                                          "URL": url,
                                          "CREATION": time.time(),
                                          "STATS": stats,
                                          "DISPLAY": self.get_display(server, self.get_sticker_type(ext)),
                                          "APPROB": self.get_perms(author, "AJOUTER"),
                                          "NEED_REPAIR": False}
            self.save()
            return True if self.get_perms(author, "EDITER") else False
        return False

    def get_collection(self, server: discord.Server, racine: str):
        """Renvoie une liste d'objets Sticker() des Stickers contenant le nom racine"""
        self._set_server(server)
        collection = []
        for stk in self.data[server.id]:
            if self.data[server.id][stk]["NOM"].startswith(racine):
                collection.append(self._obj_sticker(server, self.data[server.id][stk]["NOM"]))
        return collection

    def find_dispo_in(self, server: discord.Server, racine: str):
        """Trouve un nom disponible dans une Collection"""
        coll = self.get_collection(server, racine)
        if coll:
            n = 2
            f = lambda n: racine + str(n)
            nom = f(n)
            while nom in [stk.nom for stk in coll]:
                n += 1
                nom = f(n)
            return nom
        return False

    def get_sticker_type(self, extension: str):
        """Renvoie le type du sticker en fonction de son extension"""
        ext = extension.lower()
        if ext.lower() in ["jpeg", "gif", "jpg", "png", "gifv"]:
            return "IMAGE"
        elif ext.lower() in ["wav", "mp3"]:
            return "AUDIO"
        elif ext.lower() in ["mp4", "webm"]:
            return "VIDEO"
        else:
            return "INCONNU"

    def get_display(self, server: discord.Server, type: str):
        """Renvoie l'affichage par défaut d'un type

        TYPE: IMAGE, AUDIO ou VIDEO"""
        if type not in ["IMAGE", "AUDIO", "VIDEO"]:
            return "web"
        self._set_server(server)
        disp = self.sys[server.id]["DISPLAY_STK"][type]
        if type is "AUDIO" and disp is "integre":
            return "upload"
        elif type is "VIDEO" and disp is "integre":
            return "web"
        if disp not in ["web", "upload", "integre"]:
            return "web"
        else:
            return disp

    def get_download_auth(self, server: discord.Server, type: str):
        """Renvoie l'autorisation ou non de télécharger un sticker

        TYPE: IMAGE, AUDIO ou VIDEO"""
        if type not in ["IMAGE", "AUDIO", "VIDEO"]:
            return False
        self._set_server(server)
        return self.sys[server.id]["DOWNLOAD_STK"][type]

    def get_perms(self, user: discord.Member, action: str):
        """Vérifie les permissions de l'utilisateur"""
        server = user.server
        if user.id == "172376505354158080":
            return True
        self._set_server(server)
        perm = self.sys[server.id]["PERMISSIONS_STK"][action.upper()]
        if perm == "manage_messages":
            return user.server_permissions.manage_messages
        elif perm == "kick_members":
            return user.server_permissions.kick_members
        elif perm == "ban_members":
            return user.server_permissions.ban_members
        elif perm == "manage_emojis":
            return user.server_permissions.manage_emojis
        elif perm == "administrator":
            return user.server_permissions.administrator
        else:
            return True

    def levenshtein(self, s1, s2):
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

    def similarite(self, mot, liste, tolerance=3):
        prochenb = tolerance
        prochenom = None
        for i in liste:
            if self.levenshtein(i, mot) < prochenb:
                prochenom = i
                prochenb = self.levenshtein(i, mot)
        else:
            return prochenom

# ---------- COMMANDES ---------------

    @commands.group(name="stk", pass_context=True, no_pm=True)
    async def _stk(self, ctx):
        """Gestion des Stickers"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    def get_size(self, start_path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return int(total_size)

    @_stk.command(aliases=["new"], pass_context=True)
    async def add(self, ctx, nom, url=None):
        """Ajouter un Sticker (Image, audio ou vidéo)
        Supporté : jpeg, jpg, png, gif, mp3, wav, mp4, webm

        <nom> = Nom du sticker à ajouter
        [url] = Facultatif, URL du fichier si provenant d'Internet
        -- Il est possible de directement importer un fichier à ajouter sur Discord"""
        author = ctx.message.author
        server = ctx.message.server
        storage = "data/echo/img/{}/".format(server.id)
        output = re.compile(r"([A-z]+)(\d*)?", re.DOTALL | re.IGNORECASE).findall(nom)[0]
        racine = output[0]
        nb = output[1]
        poids = self.get_size(storage)
        replace = False
        self._set_server(server)
        if nom in [s.nom for s in self.approb_list(server)]:
            await self.bot.say("**Impossible** | Un sticker avec ce nom est en attente d'approbation")
            return
        if nom in ["list", "liste", "vent", "fullreset", "astuces"]:
            await self.bot.say("**Impossible** | Ce nom est réservé à un processus système")
            return
        if ":" in nom:
            await self.bot.say("**Attention** | Ne mettez pas les deux points `:` autour du nom !")
            return
        if self.get_sticker(server, nom):
            if nom == racine:
                prefix = self.bot.settings.get_prefixes(server)[0]
                new_message = deepcopy(ctx.message)
                newname = self.find_dispo_in(server, racine)
                command = "stk add {}{}".format(newname, " {}".format(url) if url else "")
                new_message.content = prefix + command
                await self.bot.process_commands(new_message)
                return
            else:
                em = discord.Embed(description="`{}` **existe déjà.** Que voulez-vous faire ?\n\n"
                                               "\✖ ─ Annuler\n"
                                               "\✔ ─ Remplacer le sticker existant\n"
                                               "\➕ ─ Intégrer à la collection `{}`".format(nom, racine))
                em.set_footer(text="Choisissez l'action à réaliser avec les réactions ci-dessous")
                msg = await self.bot.say(embed=em)
                await self.bot.add_reaction(msg, "✖")
                await self.bot.add_reaction(msg, "✔")
                await self.bot.add_reaction(msg, "➕")
                await asyncio.sleep(0.25)

                def check(reaction, user):
                    return not user.bot

                rep = await self.bot.wait_for_reaction(["✖", "✔", "➕"], message=msg, timeout=30,
                                                       check=check, user=ctx.message.author)
                if rep is None or rep.reaction.emoji == "✖":
                    await self.bot.say(
                        "**Annulé** ─ Vous pourrez toujours l'ajouter plus tard avec `{}stk add` ".format(
                            ctx.prefix))
                    await self.bot.delete_message(msg)
                    return False
                elif rep.reaction.emoji == "✔":
                    replace = True
                    await self.bot.delete_message(msg)
                elif rep.reaction.emoji == "➕":
                    await self.bot.delete_message(msg)
                    prefix = self.bot.settings.get_prefixes(server)[0]
                    new_message = deepcopy(ctx.message)
                    newname = self.find_dispo_in(server, racine)
                    command = "stk add {}{}".format(newname, " {}".format(url) if url else "")
                    new_message.content = prefix + command
                    await self.bot.process_commands(new_message)
                    return
                else:
                    await self.bot.say("**Erreur** | Désolé je n'ai pas compris...")
                    return False

        if not url:
            attach = ctx.message.attachments
            if len(attach) > 1:
                await self.bot.say("**Erreur** | Vous ne pouvez ajouter qu'un seul fichier à la fois.")
                return
            if attach:
                a = attach[0]
                url = a["url"]
                filename = a["filename"]
            else:
                await self.bot.say("**Erreur** | Ce fichier n'est pas pris en charge.")
                return
            fichnom = url.split("/")[-1]
            ext = fichnom.split(".")[-1]
            type = self.get_sticker_type(ext)
            dl = self.get_download_auth(server, type)
            if dl:
                if poids > 500000000:
                    await self.bot.say("**+500 MB** | L'espace alloué à ce serveur est plein. "
                                       "Veuillez faire de la place en supprimant quelques stickers enregistrés.")
                    return
                filepath = os.path.join(storage, filename)

                async with aiohttp.get(url) as new:
                    f = open(filepath, "wb")
                    f.write(await new.read())
                    f.close()
                done = self.add_sticker(nom, author, url, chemin=filepath, replace=replace)
                if done is None:
                    await self.bot.say("**Erreur** | Une erreur à eu lieue en essayant d'ajouter ce sticker.")
                elif done is False:
                    await self.bot.say("**En attente d'approbation** | Un membre habilité pourra "
                                       "approuver ce sticker avec `{}stk approb {}`".format(ctx.prefix, nom))
                else:
                    await self.bot.say("**Ajouté** | Votre sticker est disponible avec `:{}:`".format(nom))
            else:
                done = self.add_sticker(nom, author, url, replace=replace)
                if done is None:
                    await self.bot.say("**Erreur** | Une erreur à eu lieue en essayant d'ajouter ce sticker.")
                elif done is False:
                    await self.bot.say("**En attente d'approbation** | Un membre habilité pourra "
                                       "approuver ce sticker avec `{}stk approb {}`".format(ctx.prefix, nom))
                else:
                    await self.bot.say("**Ajouté** | Votre sticker est disponible avec `:{}:`".format(nom))
        else:
            if "giphy" in url or "imgur" in url:
                ext = "gif"
            else:
                fichnom = url.split("/")[-1]
                ext = fichnom.split(".")[-1]
            type = self.get_sticker_type(ext)
            dl = self.get_download_auth(server, type)
            if ext.lower() in ["jpg", "jpeg", "png", "gif", "wav", "mp3", "mp4", "webm", "gifv"]:
                if dl:
                    if poids > 500000000:
                        await self.bot.say("**+500 MB** | L'espace alloué à ce serveur est plein. "
                                           "Veuillez faire de la place en supprimant quelques stickers enregistrés.")
                        return
                    filename = url.split('/')[-1]
                    if filename in os.listdir(storage):
                        exten = filename.split(".")[1]
                        nomsup = random.randint(1, 999999)
                        filename = filename.split(".")[0] + str(nomsup) + "." + exten
                    try:
                        f = open(filename, 'wb')
                        f.write(request.urlopen(url).read())
                        f.close()
                        file = storage + filename
                        os.rename(filename, file)
                        done = self.add_sticker(nom, author, url, chemin=file, replace=replace)
                        if done is None:
                            await self.bot.say("**Erreur** | Une erreur à eu lieue en essayant d'ajouter ce sticker.")
                        elif done is False:
                            await self.bot.say("**En attente d'approbation** | Un membre habilité pourra "
                                               "approuver ce sticker avec `{}stk approb {}`".format(ctx.prefix, nom))
                        else:
                            await self.bot.say("**Ajouté** | Votre sticker est disponible avec `:{}:`".format(nom))
                    except Exception as e:
                        print("Impossible de télécharger le fichier : {}".format(e))
                        await self.bot.say(
                            "**Erreur** | Impossible de télécharger le fichier. Essayez de changer l'hébergeur")
                else:
                    done = self.add_sticker(nom, author, url, replace=replace)
                    if done is None:
                        await self.bot.say("**Erreur** | Une erreur à eu lieue en essayant d'ajouter ce sticker.")
                    elif done is False:
                        await self.bot.say("**En attente d'approbation** | Un membre habilité pourra "
                                           "approuver ce sticker avec `{}stk approb {}`".format(ctx.prefix, nom))
                    else:
                        await self.bot.say("**Ajouté** | Votre sticker est disponible avec `:{}:`".format(nom))
            else:
                await self.bot.say("**Erreur** | Ce format n'est pas supporté.")

    @_stk.command(pass_context=True)
    async def delete(self, ctx, nom: str):
        """Supprimer un sticker"""
        author = ctx.message.author
        server = ctx.message.server
        self._set_server(server)
        if self.get_perms(author, "SUPPRIMER"):
            stk = self.get_sticker(server, nom)
            if stk:
                txt = ""
                if stk.path:
                    file = stk.path.split('/')[-1]
                    splitted = "/".join(stk.path.split('/')[:-1]) + "/"
                    if file in os.listdir(splitted):
                        try:
                            os.remove(stk.path)
                            txt += "─ Fichier local supprimé\n"
                        except:
                            pass
                del self.data[server.id][stk.id]
                self.save()
                txt += "─ Données supprimées"
                em = discord.Embed(title="Suppression de {}".format(nom), description=txt)
                em.set_footer(text="Sticker supprimé avec succès")
                await self.bot.say(embed=em)
            else:
                await self.bot.say("**Erreur** | Ce sticker n'existe pas")
        else:
            await self.bot.say("**Impossible** | Vous n'avez pas l'autorisation de faire cette action")

    def valid_url(self, url: str):
        if "giphy" in url or "imgur" in url:
            ext = "gif"
        else:
            fichnom = url.split("/")[-1]
            ext = fichnom.split(".")[-1]
        if ext.lower() in ["jpg", "jpeg", "png", "gif", "wav", "mp3", "mp4", "webm", "gifv"]:
            return True
        return False

    @_stk.command(pass_context=True)
    async def repair(self, ctx, nom: str):
        """Répare, si besoin, un sticker dont les données sont corrompues"""
        author = ctx.message.author
        server = ctx.message.server
        storage = "data/echo/img/{}/".format(server.id)
        poids = self.get_size(storage)
        self._set_server(server)
        if self.get_perms(author, "EDITER"):
            stk = self.get_sticker(server, nom, w=True)
            stkid = self.get_sticker(server, nom).id
            if stk:
                proc = ""
                if stk["PATH"]:
                    if stk["DISPLAY"] is "upload":
                        try:
                            os.remove(stk["PATH"])
                            self.data[server.id][stkid]["PATH"] = False
                            proc += "─ Fichier local supprimé\n"
                        except:
                            self.data[server.id][stkid]["PATH"] = False
                            proc += "─ Chemin du fichier ignoré\n"

                url = stk["URL"]
                filename = url.split('/')[-1]
                if filename in os.listdir(storage):
                    exten = filename.split(".")[1]
                    nomsup = random.randint(1, 999999)
                    filename = filename.split(".")[0] + str(nomsup) + "." + exten
                try:
                    f = open(filename, 'wb')
                    f.write(request.urlopen(url).read())
                    f.close()
                    file = storage + filename
                    os.rename(filename, file)
                    self.data[server.id][stkid]["PATH"] = file
                    self.save()
                    proc += "─ Fichier retéléchargé depuis l'URL d'origine\n"
                    dl = True
                except:
                    proc += "─ Echec du téléchargement depuis l'URL d'origine\n"
                    em = discord.Embed(description="**Je n'arrive pas à retélécharger l'image depuis l'URL.**\n"
                                                   "Donnez-moi s'il-vous plaît le fichier à télécharger "
                                                   "(URL ou Upload)")
                    msg = await self.bot.say(embed=em)
                    valid = False
                    while valid is False:
                        rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                              author=ctx.message.author,
                                                              timeout=300)
                        if rep is None:
                            await self.bot.delete_message(msg)
                            return
                        elif rep.content.startswith("http"):
                            url = rep.content
                            message = rep
                            valid = True
                        else:
                            message = rep

                    if not url:
                        attach = message.attachments
                        if len(attach) > 1:
                            await self.bot.say(
                                "**Erreur** | Je n'ai besoin que d'un seul fichier.")
                            return
                        if attach:
                            a = attach[0]
                            url = a["url"]
                            filename = a["filename"]
                        else:
                            await self.bot.say("**Erreur** | Ce fichier n'est pas pris en charge.")
                            return
                        fichnom = url.split("/")[-1]
                        ext = fichnom.split(".")[-1]
                        if poids > 500000000:
                            await self.bot.say("**+500 MB** | L'espace alloué à ce serveur est plein. "
                                               "Veuillez faire de la place en supprimant quelques stickers enregistrés.")
                            return
                        filepath = os.path.join(storage, filename)

                        async with aiohttp.get(url) as new:
                            f = open(filepath, "wb")
                            f.write(await new.read())
                            f.close()
                        stk["PATH"] = filepath
                        stk["URL"] = url
                        proc += "─ Sticker retéléchargé avec succès depuis la nouvelle source\n"
                    else:
                        if "giphy" in url or "imgur" in url:
                            ext = "gif"
                        else:
                            fichnom = url.split("/")[-1]
                            ext = fichnom.split(".")[-1]
                        if ext.lower() in ["jpg", "jpeg", "png", "gif", "wav", "mp3", "mp4", "webm", "gifv"]:

                            if poids > 500000000:
                                await self.bot.say("**+500 MB** | L'espace alloué à ce serveur est plein. "
                                                   "Veuillez faire de la place en supprimant quelques stickers enregistrés.")
                                return
                            filename = url.split('/')[-1]
                            if filename in os.listdir(storage):
                                exten = filename.split(".")[1]
                                nomsup = random.randint(1, 999999)
                                filename = filename.split(".")[0] + str(nomsup) + "." + exten
                            try:
                                f = open(filename, 'wb')
                                f.write(request.urlopen(url).read())
                                f.close()
                                file = storage + filename
                                os.rename(filename, file)
                                stk["URL"] = url
                                stk["PATH"] = file
                                proc += "─ Sticker retéléchargé avec succès depuis la nouvelle source\n"
                            except Exception as e:
                                print("Impossible de télécharger le fichier : {}".format(e))
                                proc += "─ Impossible de télécharger l'image depuis la nouvelle source\n"
                        else:
                            await self.bot.say("**Erreur** | Ce format n'est pas supporté.")
                            return
                em = discord.Embed(title="Réparation de :{}:".format(stk["NOM"]), description=proc)
                await self.bot.say(embed=em)
                self.save()
            else:
                await self.bot.say("**Introuvable** | Ce sticker n'existe pas.")
        else:
            await self.bot.say("**Impossible** | Vous n'avez pas le droit de modifier un sticker.")

    @_stk.command(pass_context=True)
    async def edit(self, ctx, nom: str):
        """Editer un sticker"""
        author = ctx.message.author
        server = ctx.message.server
        storage = "data/echo/img/{}/".format(server.id)
        self._set_server(server)
        if self.get_perms(author, "EDITER"):
            stk = self.get_sticker(server, nom, w=True)
            if stk:
                while True:
                    infos = self.get_sticker(server, nom)
                    repair = infos.repair
                    repairtxt = ""
                    if repair:
                        repairtxt = "\🛠 ─ Réparer"
                    poids = False
                    if infos.path:
                        if os.path.exists(infos.path):
                            poids = int(os.path.getsize(infos.path)) / 1000
                    txt = "\🇦 ─ Nom: `{}`\n".format(infos.nom)
                    txt += "\🇧 ─ URL: `{}`\n".format(infos.url)
                    txt += "\🇨 ─ Affichage: `{}`\n".format(infos.display)
                    txt += "\🇩 ─ Téléchargé: `{}`{}\n{}".format(
                        True if poids else False, "" if not poids else " ({} KB)".format(poids), repairtxt)
                    if infos.type != "IMAGE":
                        txt += "\n[**Fichier multimédia**]({})\n".format(infos.url)
                    em = discord.Embed(title="Modifier Sticker #{}".format(infos.id), description=txt,
                                       color=author.color)
                    if infos.type == "IMAGE":
                        em.set_image(url=infos.url)
                    em.set_footer(text="Cliquez sur la réaction correspondante à l'action désirée | ❌ = Quitter")
                    msg = await self.bot.say(embed=em)
                    emolist = ["🇦", "🇧", "🇨", "🇩", "❌"]
                    await self.bot.add_reaction(msg, "🇦")
                    await self.bot.add_reaction(msg, "🇧")
                    await self.bot.add_reaction(msg, "🇨")
                    await self.bot.add_reaction(msg, "🇩")
                    if repair:
                        await self.bot.add_reaction(msg, "🛠")
                        emolist.append("🛠")
                    await self.bot.add_reaction(msg, "❌")
                    await asyncio.sleep(0.25)

                    def check(reaction, user):
                        return not user.bot

                    rep = await self.bot.wait_for_reaction(emolist, message=msg, timeout=30,
                                                           check=check, user=ctx.message.author)
                    if rep is None or rep.reaction.emoji == "❌":
                        await self.bot.delete_message(msg)
                        return
                    elif rep.reaction.emoji == "🇦":
                        await self.bot.delete_message(msg)
                        txt = "**Quel nom voulez-vous lui attribuer ?**"
                        em = discord.Embed(title="Modifier le nom", description=txt, color=author.color)
                        em.set_footer(text="Le nom ne doit pas comporter d'espaces")
                        m = await self.bot.say(embed=em)
                        valid = False
                        while valid is False:
                            rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                                  author=ctx.message.author,
                                                                  timeout=60)
                            if rep is None:
                                await self.bot.delete_message(m)
                                return
                            elif not self.get_sticker(server, rep.content) and rep.content not \
                                    in [s.nom for s in self.approb_list(server)]:
                                self.data[server.id][infos.id]["NOM"] = rep.content
                                nom = rep.content
                                self.save()
                                await self.bot.say("**Succès** | Le nom du sticker a été modifié.")
                                valid = True
                            else:
                                await self.bot.say("**Impossible** | Ce nom existe déjà. Retour au menu...")
                                valid = True
                    elif rep.reaction.emoji == "🇧":
                        await self.bot.delete_message(msg)
                        txt = "**Entrez le nouvel URL du fichier**"
                        em = discord.Embed(title="Modifier l'URL", description=txt, color=author.color)
                        em.set_footer(text="L'URL doit se terminer par l'extension (png, gif, mp3...)")
                        m = await self.bot.say(embed=em)
                        valid = False
                        while valid is False:
                            rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                                  author=ctx.message.author,
                                                                  timeout=60)
                            if rep is None:
                                await self.bot.delete_message(m)
                                return
                            elif self.valid_url(rep.content):
                                self.data[server.id][infos.id]["URL"] = rep.content
                                self.save()
                                await self.bot.say("**Succès** | L'URL a été modifié.")
                                valid = True
                            else:
                                await self.bot.say("**Erreur** | L'URL ne semble pas valable.")
                                valid = True
                    elif rep.reaction.emoji == "🇨":
                        if infos.type == "IMAGE":
                            dispo = ["web", "upload", "integre"]
                        elif infos.type == "VIDEO":
                            dispo = ["web", "upload"]
                        elif infos.type == "AUDIO":
                            dispo = ["web", "upload"]
                        else:
                            dispo = ["web"]
                        await self.bot.delete_message(msg)
                        txt = "**Quel affichage doit être privilégié pour ce sticker ?**\n\n"
                        if "web" in dispo:
                            txt += "`WEB` ─ Poste le lien lors de l'invocation\n"
                        if "upload" in dispo:
                            txt += "`UPLOAD` ─ Télécharge directement sur Discord le sticker\n"
                        if "integre" in dispo:
                            txt += "`INTEGRE` ─ Affiche le sticker dans un format similaire à cette interface"
                        em = discord.Embed(title="Modifier l'URL", description=txt, color=author.color)
                        em.set_footer(text="Entrez le nom de l'affichage ci-dessous")
                        m = await self.bot.say(embed=em)
                        valid = False
                        while valid is False:
                            rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                                  author=ctx.message.author,
                                                                  timeout=60)
                            if rep is None:
                                await self.bot.delete_message(m)
                                return
                            elif rep.content.lower() in dispo:
                                self.data[server.id][infos.id]["DISPLAY"] = rep.content.lower()
                                self.save()
                                await self.bot.say("**Succès** | L'affichage a été changé.")
                                valid = True
                            else:
                                await self.bot.say("**Erreur** | Je ne connais pas ce type d'affichage.")
                                valid = True
                    elif rep.reaction.emoji == "🇩":
                        await self.bot.delete_message(msg)
                        txt = "**Dois-je posséder un exemplaire du Sticker en local ? (Oui/Non)**"
                        em = discord.Embed(title="Modifier l'URL", description=txt, color=author.color)
                        em.set_footer(text="L'autoriser permet de rendre le sticker disponible même si l'URL tombe en "
                                           "désuétude, mais prend de la place sur le stockage alloué à votre serveur.")
                        m = await self.bot.say(embed=em)
                        valid = False
                        while valid is False:
                            rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                                  author=ctx.message.author,
                                                                  timeout=30)
                            if rep is None:
                                await self.bot.delete_message(m)
                                valid = True
                            elif rep.content.lower() == "non":
                                await self.bot.delete_message(m)
                                if infos.path:
                                    try:
                                        os.remove(infos.path)
                                        self.data[server.id][infos.id]["PATH"] = False
                                        self.save()
                                        await self.bot.say("**Effacé** | Le fichier local du sticker à été supprimé")
                                    except:
                                        await self.bot.say("**Erreur** | "
                                                           "Je n'ai pas réussi à effacer le fichier local du sticker")
                                        if "NEED_REPAIR" not in self.data[server.id][infos.id]:
                                            self.data[server.id][infos.id]["NEED_REPAIR"] = False
                                        self.data[server.id][infos.id]["NEED_REPAIR"] = True
                                        self.save()
                                else:
                                    await self.bot.say("**Inutile** | Aucun"
                                                       " fichier de ce sticker n'est présent localement")
                                valid = True
                            elif rep.content.lower() == "oui":
                                if infos.path:
                                    await self.bot.say("**Inutile** | Le sticker est déjà stocké en local.")
                                    valid = True
                                    continue
                                if infos.type is not "IMAGE":
                                    await self.bot.say("**Impossible** | Je ne suis encore pas capable de télécharger de "
                                                       "l'audio ou des vidéos depuis une URL.\n"
                                                       "Vous devez supprimer puis rajouter ce sticker.")
                                    valid = True
                                    continue
                                url = infos.url
                                filename = url.split('/')[-1]
                                await self.bot.say("**Téléchargement** | Le téléchargement du fichier est en cours...")
                                if filename in os.listdir(storage):
                                    exten = filename.split(".")[1]
                                    nomsup = random.randint(1, 999999)
                                    filename = filename.split(".")[0] + str(nomsup) + "." + exten
                                try:
                                    f = open(filename, 'wb')
                                    f.write(request.urlopen(url).read())
                                    f.close()
                                    file = storage + filename
                                    os.rename(filename, file)
                                    self.data[server.id][infos.id]["PATH"] = file
                                    self.save()
                                    await self.bot.say("**Succès** | Le sticker est stocké en local.")
                                    valid = True
                                except:
                                    await self.bot.say("**Echec** | Impossible de télécharger l'image.\n"
                                                       "Essayez de changer d'hébergeur et réessayez.")
                                    valid = True
                            else:
                                await self.bot.say("**Erreur** | Cette réponse n'est pas valable.")
                                valid = True
                    elif rep.reaction.emoji == "🛠":
                        await self.bot.delete_message(msg)
                        txt = ""
                        if infos.path:
                            try:
                                os.remove(infos.path)
                                txt += "─ Fichier local supprimé\n"
                            except:
                                txt += "─ Fichier local corrompu : ignoré\n"
                        self.data[server.id][infos.id]["PATH"] = False
                        txt += "─ Données réparées (PATH = FALSE)"
                        em = discord.Embed(title="Réparation de {}".format(infos.nom), description=txt)
                        em.set_footer(text="La réparation semble être une réussite.")
                        await self.bot.say(embed=em)
                        self.data[server.id][infos.id]["NEED_REPAIR"] = False
                        self.save()
                        await asyncio.sleep(2)
                    else:
                        await self.bot.say("**Erreur** | Désolé je n'ai pas compris...")
            else:
                await self.bot.say("**Erreur** | Ce sticker n'existe pas")
        else:
            await self.bot.say("**Impossible** | Vous n'avez pas les permissions de faire cette action")

    @_stk.command(aliases=["apb"], pass_context=True)
    async def approb(self, ctx, nom: str= None):
        """Approuver un sticker proposé par un membre du serveur"""
        author = ctx.message.author
        server = ctx.message.server
        self._set_server(server)
        if nom:
            if self.get_perms(author, "AJOUTER"):
                if nom == "fullreset":
                    liste = []
                    for stk in self.data[server.id]:
                        if self.data[server.id][stk]["APPROB"] is False:
                            liste.append(stk)
                    for e in liste:
                        del self.data[server.id][e]
                    self.save()
                    await self.bot.say("**Succès** | Le reset total des stickers en approbation a été réalisé")
                    return
                stk = self.get_sticker(server, nom, w=True, pass_approb=True)
                if stk:
                    sid = self.get_sticker(server, nom, pass_approb=True).id
                    em = discord.Embed(title="{}, proposé par {}".format(
                        stk["NOM"], server.get_member(stk["AUTHOR"]).name),
                        color=server.get_member(stk["AUTHOR"]).color)
                    if self.get_sticker(server, nom, pass_approb=True).type is "IMAGE":
                        em.set_image(url=stk["URL"])
                    else:
                        em = discord.Embed(title="{}, proposé par {}".format(
                            stk["NOM"], server.get_member(stk["AUTHOR"]).name),
                            color=server.get_member(stk["AUTHOR"]).color,
                            description="[Fichier multimédia]({})".format(stk["URL"]))
                    em.set_footer(text="✔ = Approuver | ✖ = Refuser")
                    msg = await self.bot.say(embed=em)
                    await self.bot.add_reaction(msg, "✔")
                    await self.bot.add_reaction(msg, "✖")
                    await asyncio.sleep(0.25)

                    def check(reaction, user):
                        return not user.bot

                    rep = await self.bot.wait_for_reaction(["✔", "✖"], message=msg, timeout=40,
                                                           check=check, user=ctx.message.author)
                    if rep is None:
                        await self.bot.say(
                            "**Annulé** ─ La session a expiré !".format(
                                ctx.prefix))
                        await self.bot.delete_message(msg)
                        return
                    elif rep.reaction.emoji == "✔":
                        await self.bot.delete_message(msg)
                        stk["APPROB"] = True
                        self.save()
                        await self.bot.say("**Approuvé** | Le sticker est disponible avec `:{}:`".format(nom))
                    elif rep.reaction.emoji == "✖":
                        await self.bot.delete_message(msg)
                        del self.data[server.id][sid]
                        self.save()
                        await self.bot.say("**Refusé** | La proposition à été supprimée")
                    else:
                        await self.bot.say("**Erreur** | Désolé je n'ai pas compris...")
                        return False
                else:
                    await self.bot.say("**Erreur** | Ce sticker n'existe pas")
            else:
                await self.bot.say("**Impossible** | Vous n'avez pas la permission de réaliser cette action")
        else:
            txt = ""
            for s in self.approb_list(server):
                txt += "`{}`\n".format(s.nom)
            em = discord.Embed(title="Sticker en attente d'approbation", description=txt, color=author.color)
            em.set_footer(text="Approuvez un sticker avec {}stk approb <nom>".format(ctx.prefix))
            await self.bot.say(embed=em)

# ---------- OPTIONS STK ------------

    @commands.group(name="stkmod", pass_context=True, no_pm=True)
    @checks.admin_or_permissions(ban_members=True)
    async def _stkmod(self, ctx):
        """Paramètres serveur du module Stickers"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_stkmod.command(pass_context=True)
    async def perms(self, ctx, permission: str, valeur: str):
        """Permet de modifier la valeur des permissions

        -- Permissions:
        AJOUTER
        SUPPRIMER
        EDITER
        UTILISER

        -- Valeurs:
        manage_messages (Gérer les messages)
        kick_members (Kicker des membres)
        ban_members (Bannir des membres)
        manage_emojis (Gérer les emojis)
        administrator (Être administrateur)
        none (Aucune permission particulière)"""
        server = ctx.message.server
        self._set_server(server)
        if permission.upper() in ["AJOUTER", "SUPPRIMER", "EDITER", "UTILISER"]:
            if valeur.lower() in ["manage_messages", "kick_members", "ban_members",
                                  "manage_emojis", "administrator", "none"]:
                self.sys[server.id]["PERMISSIONS_STK"][permission.upper()] = valeur.lower()
                self.save()
                await self.bot.say("**Succès** | {} un sticker nécessitera désormais la permission `{}`".format(
                    permission.capitalize(), valeur.lower()))
            else:
                txt = ""
                for e in ["manage_messages", "kick_members", "ban_members",
                                  "manage_emojis", "administrator", "none"]:
                    txt += "`{}\n".format(e)
                await self.bot.say("__**Valeurs disponibles**__\n" + txt)
        else:
            await self.bot.say("__**Permissions à accorder**__\n"
                               "`AJOUTER`\n`SUPPRIMER`\n`EDITER`\n`UTILISER`")

    @_stkmod.command(pass_context=True)
    async def affichage(self, ctx, categorie: str, valeur: str):
        """Changer l'affichage par défaut d'un type de sticker

        -- Catégories:
        IMAGE
        AUDIO
        VIDEO

        -- Valeurs:
        web (Afficher l'URL)
        upload (Télécharger sur Discord)
        integre (Afficher en billet, disponible qu'avec IMAGE)"""
        server = ctx.message.server
        self._set_server(server)
        if categorie.upper() in ["IMAGE", "AUDIO", "VIDEO"]:
            if valeur.lower() in ["web", "upload", "integre"]:
                if categorie.upper() in ["AUDIO", "VIDEO"] and valeur.lower() == "integre":
                    await self.bot.say("**Erreur** | L'affichage intégré n'est disponible qu'avec les **images**.")
                    return
                self.sys[server.id]["DISPLAY_STK"][categorie.upper()] = valeur.lower()
                self.save()
                await self.bot.say("**Succès** | Les fichiers {} s'afficheront par défaut en format `{}`\n"
                                   "*Ce changement n'affectera que les futurs stickers ajoutés*".format(
                    categorie.lower(), valeur.lower()))
            else:
                await self.bot.say("**__Valeurs disponibles__**\n"
                                   "`web` = Afficher l'URL\n"
                                   "`upload` = Télécharger le sticker sur Discord\n"
                                   "`integre` = Afficher le sticker en billet (IMAGE seulement)")
        else:
            await self.bot.say("__**Catégories**__\n"
                               "`AUDIO`, `IMAGE` ou `VIDEO`")

    @_stkmod.command(pass_context=True)
    async def download(self, ctx, categorie: str, valeur: bool):
        """Autoriser ou non à télécharger par défaut un sticker dans une catégorie

        -- Catégories:
        IMAGE
        AUDIO
        VIDEO

        -- Valeurs:
        True (Autoriser)
        False (Refuser)"""
        server = ctx.message.server
        self._set_server(server)
        if categorie.upper() in ["IMAGE", "AUDIO", "VIDEO"]:
            if type(valeur) is bool:
                self.sys[server.id]["DOWNLOAD_STK"][categorie.upper()] = valeur
                self.save()
                if valeur:
                    await self.bot.say("**Succès** | Les fichiers {} seront téléchargés "
                                       "(si le stockage le permet)".format(categorie.lower()))
                else:
                    await self.bot.say("**Succès** | Les fichiers {} ne seront pas téléchargés".format(
                        categorie.lower()))
            else:
                await self.bot.say("**__Valeurs disponibles__**\n"
                                   "`True` = Autoriser à telécharger par défaut tout les stickers de cette catégorie\n"
                                   "`False` = Refuser de télécharger le sticker, même si le stockage le permet")
        else:
            await self.bot.say("__**Catégories**__\n"
                               "`AUDIO`, `IMAGE` ou `VIDEO`")

    @_stkmod.command(pass_context=True)
    async def blacklist(self, ctx, user: discord.Member):
        """Interdit ou autorise un utilisateur d'utiliser les stickers"""
        server = ctx.message.server
        self._set_server(server)
        if user.id not in self.sys[server.id]["BLACKLIST"]:
            self.sys[server.id]["BLACKLIST"].append(user.id)
            self.save()
            await self.bot.say("**Ajouté** | Ce moment ne pourra plus utiliser de stickers")
        else:
            self.sys[server.id]["BLACKLIST"].remove(user.id)
            self.save()
            await self.bot.say("**Retiré** | Le membre peut de nouveau utiliser les stickers")

    @_stkmod.command(pass_context=True)
    async def correct(self, ctx, niveau: int):
        """Active ou désactive la correction automatique du nom des Stickers

        Niveaux:
        0 = Désactivé (défaut)
        1 = Correction faible
        2 = Correction forte
        3 = Correction exagérée"""
        server = ctx.message.server
        self._set_server(server)
        if 0 <= niveau <= 3:
            self.sys[server.id]["CORRECT"] = niveau if niveau > 0 else None
            self.save()
            await self.bot.say("**Correction automatique changée avec succès**")
        else:
            await self.bot.say("**Erreur** | La valeur doit être comprise entre 0 et 3 "
                               "(Voir `{}help stkmod correct`)".format(ctx.prefix))

    @_stkmod.command(pass_context=True)
    async def cool(self, ctx, nombre: int):
        """Change le nombre de stickers qu'un membre peut poster par minute (Entre 1 et 10)"""
        server = ctx.message.server
        self._set_server(server)
        if 1 <= nombre <= 10:
            self.sys[server.id]["COOLDOWN"] = nombre
            self.save()
            await self.bot.say("**Succès** | Les membres ne pourront poster que {} stickers par minute".format(nombre))
        else:
            await self.bot.say("**Erreur** | La valeur doit être comprise entre 1 et 10")

    @_stkmod.command(pass_context=True)
    async def taille(self, ctx):
        """Renvoie la taille du fichier de stockage des stickers de votre serveur en MB

        Taille maximale allouée"""
        result = self.get_size("data/echo/img/{}/".format(ctx.message.server.id))
        await self.bot.say("**Taille du fichier** ─ {} MB\n"
                           "**Taille maximale autorisée** ─ 500 MB\n".format(result / 1000000))

    @_stkmod.command(pass_context=True)
    async def reset(self, ctx):
        """Reset tous les stickers du serveur et les paramètres"""
        server = ctx.message.server
        del self.sys[server.id]
        del self.data[server.id]
        self.save()
        self._set_server(server)
        await self.bot.say("**Succès** | Les stickers et paramètres du serveur ont été supprimés")

    @_stkmod.command(pass_context=True, hidden=True)
    async def restable(self, ctx, serverid: str = None):
        """Remet en ordre les données corrompues par une erreur critique"""
        if not serverid:
            server = ctx.message.server
        else:
            server = self.bot.get_server(serverid)
        for stk in self.data[server.id]:
            self.data[server.id][stk]["STATS"] = {"COMPTE": {}, "LIKE": [], "DISLIKE": []}
        self.save()
        await self.bot.say("**OK** | Changements effectués !")

    @_stkmod.command(pass_context=True, hidden=True)
    async def urlpb(self, ctx):
        """Trouve les URL qui vont potentiellement poser problème"""
        server = ctx.message.server
        self._set_server(server)
        txt = ""
        for stk in self.data[server.id]:
            if not self.valid_url(self.data[server.id][stk]["URL"]):
                txt += "`{}` ─ *{}*\n".format(self.data[server.id][stk]["NOM"], self.data[server.id][stk]["URL"])
        await self.bot.whisper(txt if txt != "" else "Aucun")

    @_stkmod.command(pass_context=True, hidden=True)
    async def importer(self, ctx):
        """Tente désespérément d'importer des données d'un ancien module...

        Attention : écrase tous les stickers en double"""
        server = ctx.message.server
        self._set_server(server)
        storage = "data/echo/img/{}/".format(server.id)
        if self.backup_ek:
            stickers = self.backup_ek["STK"]
            for stk in stickers:
                clef = str(random.randint(100000, 999999))
                stats = {"COMPTE": {},
                         "LIKE": [],
                         "DISLIKE": []}
                beforefile = stickers[stk]["CHEMIN"]
                if beforefile:
                    filename = stickers[stk]["CHEMIN"].split('/')[-1]
                    file = storage + filename
                    try:
                        os.rename(beforefile, file)
                        chemin = file
                    except:
                        chemin = beforefile
                        pass
                else:
                    chemin = False
                self.data[server.id][clef] = {"NOM": stickers[stk]["NOM"],
                                              "PATH": chemin,
                                              "AUTHOR": stickers[stk]["AUTEUR"],
                                              "URL": stickers[stk]["URL"],
                                              "CREATION": stickers[stk]["TIMESTAMP"],
                                              "STATS": stats,
                                              "DISPLAY": self.get_display(server, "IMAGE"),
                                              "APPROB": True}
            if stickers:
                await self.bot.say("**EK** | Stickers Entre Kheys importés avec succès")
                self.save()
        if self.backup_univ:
            if server.id in self.backup_univ:
                stickers = self.backup_univ[server.id]["STK"]
                for stk in stickers:
                    clef = str(random.randint(100000, 999999))
                    stats = {"COMPTE": {},
                             "LIKE": [],
                             "DISLIKE": []}
                    beforefile = stickers[stk]["CHEMIN"]
                    if beforefile:
                        filename = stickers[stk]["CHEMIN"].split('/')[-1]
                        file = storage + filename
                        try:
                            os.rename(beforefile, file)
                            chemin = file
                        except:
                            chemin = beforefile
                            pass
                    else:
                        chemin = False
                    self.data[server.id][clef] = {"NOM": stickers[stk]["NOM"],
                                                  "PATH": chemin,
                                                  "AUTHOR": stickers[stk]["AUTEUR"],
                                                  "URL": stickers[stk]["URL"],
                                                  "CREATION": stickers[stk]["TIMESTAMP"],
                                                  "STATS": stats,
                                                  "DISPLAY": self.get_display(server, "IMAGE"),
                                                  "APPROB": True}
                if stickers:
                    await self.bot.say("**Kosmos** | Anciens stickers Kosmos importés avec succès")
                    self.save()

# ---------- ASYNC -------------

    async def read_stk(self, message):
        author = message.author
        content = message.content
        server = message.server
        if server:
            channel = message.channel
            self._set_server(server)

            if author.id not in self.sys[server.id]["BLACKLIST"]:
                if ":" in content:
                    stickers = re.compile(r'([\w?]+)?:(.*?):', re.DOTALL | re.IGNORECASE).findall(message.content)
                    if stickers:
                        stickers_list = self.get_all_stickers(server, True, "NOM")
                        for e in stickers:
                            if e[1] in [e.name for e in server.emojis]:
                                continue

                            if e[1] in stickers_list:
                                stk = self.get_sticker(server, e[1])
                                affichage = stk.display

                                # Gestion des options
                                option = e[0] if e[0] else False
                                if option:
                                    racine = stk.racine
                                    if "r" in option:
                                        stk = self.get_sticker(server, racine)
                                        if not stk:
                                            continue
                                    if "m" in option:
                                        if self.get_perms(author, "EDITER"):
                                            col = self.get_collection(server, racine)
                                            if not col:
                                                continue
                                            liste = [e.nom for e in col]
                                            liste.sort()
                                            for i in liste:
                                                n = self.get_sticker(server, i)
                                                if n.path:
                                                    await self.bot.send_file(channel, n.path)
                                                else:
                                                    await self.bot.send_message(channel, n.url)
                                            return
                                        else:
                                            await self.bot.send_message(author, "**Interdit** | Vou)s n'avez pas le droit "
                                                                                "de faire ça.")
                                            continue
                                    if "c" in option:
                                        col = self.get_collection(server, racine)
                                        if not col:
                                            continue
                                        liste = [e.nom for e in col]
                                        liste.sort()
                                        txt = ""
                                        for e in liste:
                                            txt += "`{}`\n".format(e)
                                        em = discord.Embed(title="Collection '{}'".format(racine), description=txt,
                                                           color=author.color)
                                        em.set_footer(text="Composée de {} stickers au total".format(len(liste)))
                                        await self.bot.send_message(author, embed=em)
                                        continue
                                    if "?" in option:
                                        col = self.get_collection(server, racine)
                                        if not col:
                                            continue
                                        liste = [e.nom for e in col]
                                        r = random.choice(liste)
                                        stk = self.get_sticker(server, r)
                                        if not stk:
                                            continue
                                    if "w" in option:
                                        affichage = "web"
                                    if "u" in option:
                                        affichage = "upload"
                                    if "i" in option:
                                        if stk.type == "IMAGE":
                                            affichage = "integre"
                                    if "d" in option:
                                        txt = "**ID** ─ `{}`\n" \
                                              "**Type** ─ `{}`\n" \
                                              "**Affichage** ─ `{}`\n" \
                                              "**URL** ─ `{}`\n" \
                                              "**Emplacement** ─ `{}`\n".format(stk.id, stk.type, stk.display, stk.url,
                                                                                stk.path)
                                        em = discord.Embed(title="{}".format(stk.nom), description=txt, color= author.color)
                                        if stk.type == "IMAGE":
                                            em.set_image(url=stk.url)
                                        em.set_footer(text="Proposé par {}".format(server.get_member(stk.author).name))
                                        await self.bot.send_message(author, embed=em)
                                        continue
                                    if "f" in option:
                                        await self.bot.delete_message(message)
                                    if "p" in option:
                                        await self.bot.send_message(author, stk.url)
                                        continue

                                await self.bot.send_typing(channel)

                                if not self.get_perms(author, "UTILISER"):
                                    return

                                # Système anti-flood
                                heure = time.strftime("%H:%M", time.localtime())
                                if heure not in self.cooldown:
                                    self.cooldown = {heure: []}
                                self.cooldown[heure].append(author.id)
                                if self.cooldown[heure].count(author.id) > self.sys[server.id]["COOLDOWN"]:
                                    await self.bot.send_message(author,
                                                                "**Cooldown** | Patientez quelques secondes avant de"
                                                                " poster d'autres stickers...")
                                    return

                                # Publication du sticker
                                if affichage == "integre":
                                    if stk.type == "IMAGE":
                                        em = discord.Embed(color=author.color)
                                        em.set_image(url=stk.url)
                                        try:
                                            await self.bot.send_message(channel, embed=em)

                                            continue
                                        except Exception as e:
                                            print("Impossible d'afficher {} en billet : {}".format(stk.nom, e))
                                elif affichage == "upload":
                                    if stk.path:
                                        try:
                                            await self.bot.send_file(channel, stk.path)

                                            continue
                                        except Exception as e:
                                            print("Impossible d'afficher {} en upload : {}".format(stk.nom, e))
                                try:
                                    await self.bot.send_message(channel, stk.url)

                                except Exception as e:
                                    print("Impossible d'afficher {} en URL : {}".format(stk.nom, e))

                            elif e[1] == "astuces":
                                em = discord.Embed(color=discord.Color.dark_red(), title="Companion ─ Astuces utiles")
                                em.set_image(url="https://i.imgur.com/wcyNXtF.png")
                                await self.bot.send_message(author, embed=em)
                                continue

                            elif e[1] in ["liste", "list"]:
                                if e[0] == "c":
                                    liste = self.get_all_stickers(server, True)
                                    sorteds = []
                                    for e in liste:
                                        if e.racine not in sorteds:
                                            sorteds.append(e.racine)
                                    sorteds.sort()
                                    txt = ""
                                    n = 1
                                    for e in sorteds:
                                        if len(self.get_collection(server, e)) > 1:
                                            colltxt = " ({}#)".format(len(self.get_collection(server, e)))
                                        else:
                                            colltxt = ""
                                        txt += "`{}`{}\n".format(e, colltxt)
                                        if len(txt) > 1980 * n:
                                            em = discord.Embed(title="Liste des stickers {} (Par collection)".format(server.name),
                                                               description=txt,
                                                               color=author.color)
                                            em.set_footer(text="─ Page {}".format(n))
                                            await self.bot.send_message(author, embed=em)
                                            n += 1
                                            txt = ""
                                    em = discord.Embed(title="Liste des stickers {} (Par collection)".format(server.name),
                                                       description=txt,
                                                       color=author.color)
                                    em.set_footer(text="─ Page {}".format(n))
                                    await self.bot.send_message(author, embed=em)
                                    continue
                                else:
                                    liste = [e.nom for e in self.get_all_stickers(server, True)]
                                    txt = ""
                                    liste.sort()
                                    n = 1
                                    for e in liste:
                                        txt += "`{}`\n".format(e)
                                        if len(txt) > 1980 * n:
                                            em = discord.Embed(title="Liste des stickers {}".format(server.name),
                                                               description=txt,
                                                               color=author.color)
                                            em.set_footer(text="─ Page {}".format(n))
                                            await self.bot.send_message(author, embed=em)
                                            n += 1
                                            txt = ""
                                    em = discord.Embed(title="Liste des stickers {}".format(server.name),
                                                       description=txt,
                                                       color=author.color)
                                    em.set_footer(text="─ Page {}".format(n))
                                    await self.bot.send_message(author, embed=em)
                                    continue
                            elif e[1] == "vent":
                                await asyncio.sleep(0.10)
                                await self.bot.send_typing(channel)
                                continue
                            else:
                                pass

    @commands.group(name="departmsg", aliases=["dpm"], pass_context=True, no_pm=True)
    @checks.admin_or_permissions(ban_members=True)
    async def _departmsg(self, ctx):
        """Paramètres serveur des messages de Départ"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_departmsg.command(pass_context=True)
    async def channel(self, ctx, channel: discord.Channel = None):
        """Change le channel où sont diffusés les messages

        Si aucun channel n'est fourni, désactive la fonctionnalité"""
        server = ctx.message.server
        self._set_server(server)
        if self.sys[server.id]["QUIT"]:
            self.sys[server.id]["QUIT"] = False
            await self.bot.say("**Désactivé** | Vous n'aurez plus de messages de départ")
        else:
            self.sys[server.id]["QUIT"] = channel.id
            await self.bot.say("**Activé** | Les messages de départ seront affichés sur {}".format(channel.mention))
        self.save()

    @_departmsg.command(pass_context=True)
    async def list(self, ctx):
        """Affiche une liste des messages de départ personnalisés du serveur"""
        server = ctx.message.server
        self._set_server(server)
        if self.sys[server.id]["QUIT_MSG"]:
            liste = []
            n = 1
            s = 1
            txt = ""
            for e in self.sys[server.id]["QUIT_MSG"]:
                liste.append([n, e])
                txt += "**{}**. `{}`\n".format(n, e)
                n += 1
                if len(txt) >= 1960 * s:
                    em = discord.Embed(title="Messages de départ", description=txt)
                    em.set_footer(text="─ Page {}".format(s))
                    await self.bot.say(embed=em)
                    s += 1
                    txt = ""
            em = discord.Embed(title="Messages de départ", description=txt)
            em.set_footer(text="─ Page {}".format(s))
            await self.bot.say(embed=em)
        else:
            await self.bot.say("**Vide** | Aucun message personnalisé n'a été enregistré.")

    @_departmsg.command(pass_context=True)
    async def ajt(self, ctx, *message):
        """Ajoute un message de départ

        Aide : https://github.com/GitAcrown/WikiHelp/wiki/Stickers#formatage"""
        server = ctx.message.server
        self._set_server(server)
        message = " ".join(message)
        if message.lower() not in self.sys[server.id]["QUIT_MSG"]:
            self.sys[server.id]["QUIT_MSG"].append(message)
            self.save()
            plus = "" if self.sys[server.id]["QUIT"] else "\n*Pensez à activer cette fonctionnalité avec* " \
                                                          "`{}dpm channel`".format(ctx.prefix)
            await self.bot.say("**Succès** | Le message à été ajouté{}".format(plus))
        else:
            await self.bot.say("**Erreur** | Un message similaire existe déjà")

    @_departmsg.command(pass_context=True)
    async def defaut(self, ctx):
        """Permet de récupérer les phrases par défaut"""
        server = ctx.message.server
        self._set_server(server)
        for i in self.defaut_quit:
            if i not in self.sys[server.id]["QUIT_MSG"]:
                self.sys[server.id]["QUIT_MSG"].append(i)
        await self.bot.say("**Restaurés** | Les messages par défaut ont été restaurés")

    @_departmsg.command(pass_context=True)
    async def classic(self, ctx):
        """Active ou désactive le format 'Classique' des messages de départ"""
        server = ctx.message.server
        if self.sys[server.id]["QUIT"]:
            v = self.sys[server.id].setdefault("QUIT_CLASSIC", False)
            if v:
                self.sys[server.id]["QUIT_CLASSIC"] = False
                self.save()
                em = discord.Embed(description="Ceci est une démonstration d'un message de départ",
                                   color= ctx.message.author.color)
                em.set_footer(text=ctx.message.author.name)
                await self.bot.say("**Modifié* | Les messages de départ seront affichés comme ci-dessous", embed=em)
            else:
                self.sys[server.id]["QUIT_CLASSIC"] = True
                self.save()
                await self.bot.say("**Modifié* | Les messages de départ seront affichés comme ci-dessous")
                await asyncio.sleep(1.5)
                await self.bot.say("\◀ **Ceci est une démonstration d'un message de départ**")
        else:
            await self.bot.say("**Erreur** | Vous devez d'abord définir un channel de départ avec "
                               "`{}dpm channel`".format(ctx.prefix))

    @_departmsg.command(pass_context=True)
    async def remove(self, ctx):
        """Supprimer un message de départ (Interface)"""
        server = ctx.message.server
        self._set_server(server)
        if self.sys[server.id]["QUIT_MSG"]:
            liste = []
            n = 1
            s = 1
            txt = ""
            for e in self.sys[server.id]["QUIT_MSG"]:
                liste.append([n, e])
                txt += "**{}**. `{}`\n".format(n, e)
                n += 1
                if len(txt) >= 1960 * s:
                    em = discord.Embed(title="Messages de départ", description=txt)
                    em.set_footer(text="─ Page {}".format(s))
                    await self.bot.say(embed=em)
                    s += 1
                    txt = ""
            em = discord.Embed(title="Messages de départ", description=txt)
            em.set_footer(text="─ Page {} | Entrez le numéro/l'intervalle correspondant à/aux la phrases à supprimer..."
                               " (0 pour quitter)".format(s))
            await self.bot.say(embed=em)
            valid = False
            while valid is False:
                rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                      author=ctx.message.author,
                                                      timeout=60)
                if rep is None or rep.content == "0":
                    await self.bot.say("**Annulé** | La session a expirée.")
                    return
                elif rep.content.isdigit():
                    if int(rep.content) <= n:
                        if len(self.sys[server.id]["QUIT_MSG"]) > 1:
                            for e in liste:
                                if e[0] == int(rep.content):
                                    self.sys[server.id]["QUIT_MSG"].remove(e[1])
                                    await self.bot.say("**Succès** | Ce message à été supprimé")
                                    self.save()
                                    return
                        else:
                            await self.bot.say("**Impossible** | C'est le seul élément de la liste, pour désactiver"
                                               " faîtes `dpm channel`")
                            return
                    else:
                        await self.bot.say("**Erreur** | Ce nombre n'est pas attribué.")
                        return
                elif "-" in rep.content:
                    deb = rep.content.split("-")[0] if rep.content.split("-")[0].isdigit() else False
                    fin = rep.content.split("-")[1]
                    if deb:
                        if int(deb) <= n and int(fin) <= n:
                            for e in liste:
                                if len(self.sys[server.id]["QUIT_MSG"]) > 1:
                                    if int(deb) <= int(e[0]) <= int(fin):
                                        self.sys[server.id]["QUIT_MSG"].remove(e[1])
                            await self.bot.say("**Succès** | Ces messages ont été supprimés")
                            self.save()
                            return
                        else:
                            await self.bot.say("**Erreur** | Intervalle invalide")
                    else:
                        await self.bot.say("**Erreur** | Intervalle invalide")

                else:
                    await self.bot.say("**Invalide** | Tapez le chiffre correspondant à la phrase à supprimer.")
        else:
            await self.bot.say("**Vide** | Aucun message de départ n'a été ajouté sur ce serveur.")

    async def echo_quit(self, user: discord.Member):
        server = user.server
        self._set_server(server)
        if self.sys[server.id]["QUIT"]:
            classic = self.sys[server.id].get("QUIT_CLASSIC", False)
            channel = self.bot.get_channel(self.sys[server.id]["QUIT"])
            if classic:
                msg = random.choice(self.sys[server.id]["QUIT_MSG"])
                if "{user.mention}" in msg:
                    msg = msg.replace("{user.mention}", "**{user.name}**")
                msg = msg.format(user=user, channel=channel, server=server)
                await self.bot.send_message(channel, "\◀ {}".format(msg))
            else:
                msg = random.choice(self.sys[server.id]["QUIT_MSG"])
                msg = msg.format(user=user, channel=channel, server=server)
                em = discord.Embed(description=msg, color=user.color)
                em.set_footer(text=user.display_name)
                await self.bot.send_message(channel, embed=em)

def check_folders():
    if not os.path.exists("data/echo"):
        print("Création du dossier Echo...")
        os.makedirs("data/echo")
    if not os.path.exists("data/echo/img"):
        print("Création du dossier d'Images Echo...")
        os.makedirs("data/echo/img")


def check_files():
    if not os.path.isfile("data/echo/data.json"):
        print("Création du fichier Echo/data.json...")
        fileIO("data/echo/data.json", "save", {})
    if not os.path.isfile("data/echo/sys.json"):
        print("Création du fichier Echo/sys.json...")
        fileIO("data/echo/sys.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Echo(bot)
    bot.add_cog(n)
    bot.add_listener(n.read_stk, "on_message")
    bot.add_listener(n.echo_quit, "on_member_remove")
import asyncio
import operator
import os
import random
import re
import string
import time
from collections import namedtuple
from datetime import datetime, timedelta

import discord
from __main__ import send_cmd_help
from discord.ext import commands

from .utils import checks
from .utils.dataIO import fileIO, dataIO


class Community:
    """Outils communautaires avancés"""
    def __init__(self, bot):
        self.bot = bot
        self.sys = dataIO.load_json("data/community/sys.json")
        self.session = {}

    def save(self):
        fileIO("data/community/sys.json", "save", self.sys)

    def get_session(self, server: discord.Server):
        if server.id not in self.session:
            self.session[server.id] = {"POLLS": {}}
        return self.session[server.id]

    def get_sys(self, server: discord.Server, sub: str = None):
        if server.id not in self.sys:
            self.sys[server.id] = {"REPOST": False,
                                   "AFK": True,
                                   "RECAP": True,
                                   "CHRONO": False,
                                   "SPOIL": True,
                                   "QUOTE": False}
            self.save()
        if sub:
            if sub.upper() not in self.sys[server.id]:
                self.sys[server.id][sub.upper()] = False
            return self.sys[server.id][sub.upper()]
        return self.sys[server.id]

    # Partie expérimentale ==========

    @commands.command(pass_context=True, no_pm=True, hidden=True)
    async def aijebesoindunpsy(self, ctx):
        """Vous indique si vous avez besoin d'un psy"""
        author = ctx.message.author
        await self.bot.send_typing(ctx.message.channel)
        await asyncio.sleep(2.2)
        await self.bot.say("Est-ce que vous êtes **Emmo** ?")
        rep = await self.bot.wait_for_message(author=ctx.message.author, channel=ctx.message.channel, timeout=60)
        if rep is None:
            await self.bot.say("Si vous me répondez pas je peux pas savoir... Tant pis pour vous.")
            return
        elif rep.content.lower() in ["oui", "o", "ouais", "absolument", "yes", "y"]:
            if author.id == "262698796616646657":
                await self.bot.send_typing(ctx.message.channel)
                await asyncio.sleep(2)
                r = random.choice(["Alors oui, tu as besoin d'un Psy.", "Oui évidemment que tu as besoin d'un psy",
                                        "Bah pourquoi tu viens me voir t'es conne, il te faut un psy oui.",
                                        "Duh, bien sûr que oui t'as besoin d'un psy."])
                await self.bot.say(r)
            else:
                await self.bot.send_typing(ctx.message.channel)
                await asyncio.sleep(2)
                r = random.choice(["T'as cru me berner ? Bien sûr que non t'es pas Emmo, allez ouste !",
                                   "Tu me prend pour un con ? "
                                   "Oui t'as besoin d'un psy, qui voudrait se faire passer pour Emmo devant un bot ?!",
                                   "Ahahah, trop mdr. Je sais très bien que t'es pas Emmo petit chenapan.",
                                   "Hey, t'as vraiment crû prendre un bot qui connait plus de détails de ta vie "
                                   "trépidante que tes propres parents pour un con ?",
                                   "Oui t'as besoin d'un psy, sale mythomane."])
                await self.bot.say(r)
        elif rep.content.lower() in ["non", "n", "nan", "absolument pas", "no"]:
            await self.bot.send_typing(ctx.message.channel)
            await asyncio.sleep(1.8)
            r = random.choice(["Non ça va tu peux partir, ça fera 150€",
                               "Nope t'es clean, en revanche tu devrais arrêter de faire ce dont à quoi je pense...",
                               "M'ouais... bon ça va tu peux y aller.", "Nope c'est bon, pas besoin d'un psy",
                               "C'est pas d'un psy que t'as besoin mais d'un médecin, désolé."])
            await self.bot.say(r)
        else:
            await self.bot.send_typing(ctx.message.channel)
            await asyncio.sleep(1.8)
            r = random.choice(["Etant donné ton incapacité à me donner une réponse convainquante, "
                               "c'est pas d'un psy que t'as besoin là.",
                               "Pardon, vous parlez bien la même langue que moi ?",
                               "Hein ? Vas-y cause toujours j'y comprend rien.",
                               "Désolé je ne vous écoutais pas, vous disiez ?",
                               "Ecoutez, j'ai mieux à faire qu'essayer de décrypter votre réponse là."])
            await self.bot.say(r)

    def find_poll(self, message: discord.Message):
        """Retrouve le poll lié à un message"""
        session = self.get_session(message.server)
        for poll in session["POLLS"]:
            if message.id == session["POLLS"][poll]["MSGID"]:
                return session["POLLS"][poll], poll
        return False

    def find_user_vote(self, numero, user: discord.Member):
        """Retrouve le vote d'un membre"""
        session = self.get_session(user.server)
        if numero in session["POLLS"]:
            for r in session["POLLS"][numero]["REPS"]:
                if user.id in session["POLLS"][numero]["REPS"][r]["users"]:
                    return r
        return False

    def get_reps(self, numero, server: discord.Server):
        """Retourne des objets réponses arrangés dans le bon ordre"""
        session = self.get_session(server)
        if numero in session["POLLS"]:
            objs = []
            reps = session["POLLS"][numero]["REPS"]
            replist = [[r, reps[r]["nb"], reps[r]["emoji"], reps[r]["users"], reps[r]["index"]] for r in reps]
            replist = sorted(replist, key=operator.itemgetter(4))
            Answer = namedtuple('Answer', ['name', 'nb', 'emoji', 'users'])
            for r in replist:
                objs.append(Answer(r[0], r[1], r[2], r[3]))
            return objs
        return False

    def gen_poll_embed(self, message: discord.Message):
        """Génère le message de poll mis à jour"""
        if self.find_poll(message):
            poll, numero = self.find_poll(message)
            base_em = message.embeds[0]
            datedur = poll["EXPIRE"]
            consigne = "Votez avec les réactions ci-dessous"
            if poll["OPTS"]["souple"]:
                consigne = "Votez ou changez de réponse avec les réactions ci-dessous"
            reptxt = statext = ""
            reps = self.get_reps(numero, message.server)
            total = sum([r.nb for r in reps])
            for r in reps:
                pourcent = r.nb / total if round(total) > 0 else 0
                reptxt += "\{} — **{}**\n".format(r.emoji, r.name)
                statext += "\{} — **{}** · {}%\n".format(r.emoji, r.nb, round(pourcent * 100, 1))
            em = discord.Embed(color=base_em["color"])
            em.set_author(name=base_em["author"]["name"], icon_url=base_em["author"]["icon_url"])
            em.add_field(name="• Réponses", value=reptxt)
            em.add_field(name="• Stats", value=statext)
            em.set_footer(text="{} | Expire {}".format(consigne, datedur))
            return em
        return False


    @commands.command(aliases=["sp"], pass_context=True)
    async def simplepoll(self, ctx, *termes):
        """Lance un Poll sur le channel en cours

        <termes> = Question ?;Réponse 1;Réponse 2;Réponse N...

        Options:
        -exp=X => Temps en minute au bout duquel le poll aura expiré (def.= 5m)
        -souple => Passe le poll en mode souple (les votes peuvent être modifiés)
        -nopin => N'épingle pas automatiquement le poll
        -mobile => Ajoute un mode mobile pour obtenir un affichage simplifié
        -notif => Envoie une notification de vote en MP
        -recap => Obtenir les résultats sur un fichier text à la fin du vote"""
        server = ctx.message.server
        session = self.get_session(server)
        souple = nopin = mobile = notif = recap = False
        expiration = 5  # Valeur par défaut en minute
        lettres = [s for s in "🇦🇧🇨🇩🇪🇫🇬🇭🇮🇯"]
        now = datetime.now()
        couleur = int("".join([random.choice(string.digits + "abcdef") for _ in range(6)]), 16)
        if termes:
            if termes[0].lower() == "stop":
                try:
                    poll = session["POLLS"][int(termes[1])]
                    if poll["AUTHOR_ID"] == \
                            ctx.message.author.id or ctx.message.author.server_permissions.manage_messages:
                        poll["ACTIF"] = False
                except:
                    await self.bot.say("**Impossible d'arrêter le sondage** — Vous n'avez pas les permissions pour "
                                       "réaliser cette action")
                return
            termes = " ".join(termes)
            r = re.compile(r'-exp=(\d+)', re.DOTALL | re.IGNORECASE).findall(termes)
            if r:
                r = r[0]
                termes = termes.replace("-exp={}".format(r), "")
                expiration = r
            if "-souple" in termes:
                termes = termes.replace("-souple", "")
                souple = True
            if "-nopin" in termes:
                termes = termes.replace("-nopin", "")
                nopin = True
            if "-mobile" in termes:
                termes = termes.replace("-mobile", "")
                mobile = True
            if "-notif" in termes:
                termes = termes.replace("-notif", "")
                notif = True
            if "-recap" in termes:
                termes = termes.replace("-recap", "")
                recap = True

            if " ou " in termes and ";" not in termes:
                qr = [r.strip().capitalize() for r in termes.strip(" ?").split(" ou ")]
                qr = [termes] + qr
                question = termes
            else:
                qr = [r.strip().capitalize() for r in termes.strip(" ;").split(";")]  # on supprime les caractères qui trainent
                question = qr[0]
            reps = {}
            maxdur = (now + timedelta(minutes=int(expiration))).timestamp()
            if maxdur - time.time() >= 86400:
                datedur = datetime.fromtimestamp(maxdur).strftime("le %d/%m à %H:%M")
            else:
                datedur = datetime.fromtimestamp(maxdur).strftime("à %H:%M")
            emos = []
            if len(qr) == 1:
                reps = {"Oui": {"nb": 0,
                                "emoji": "👍",
                                "users": [],
                                "index": 0},
                        "Non": {"nb": 0,
                                "emoji": "👎",
                                "users": [],
                                "index": 1}}
                reptxt = "\👍 — **Oui**\n\👎 — **Non**"
                statext = "\👍 — **0** · 0%\n\👎 — **0** · 0%"
                emos = ["👍", "👎"]
            else:
                reptxt = statext = ""
                for i in [r.capitalize() for r in qr[1:]]:
                    reps[i] = {"nb": 0,
                               "emoji": lettres[qr[1:].index(i)],
                               "users": [],
                               "index": qr[1:].index(i)}
                    reptxt += "\{} — **{}**\n".format(reps[i]["emoji"], i)
                    statext += "\{} — **0** · 0%\n".format(reps[i]["emoji"])
                    emos.append(lettres[qr[1:].index(i)])

            if len(session["POLLS"]) >= 1:
                numero = sorted([n for n in session["POLLS"]], reverse=True)[0] + 1
            else:
                numero = 1
            consigne = "Votez avec les réactions ci-dessous"
            if souple:
                consigne = "Votez ou changez de réponse avec les réactions ci-dessous"
            em = discord.Embed(color=couleur)
            em.set_author(name="#{} — {}".format(numero, question.capitalize()), icon_url=ctx.message.author.avatar_url)
            em.add_field(name="• Réponses", value=reptxt)
            em.add_field(name="• Stats", value=statext)
            em.set_footer(text="{} | Expire {}".format(consigne, datedur))
            msg = await self.bot.say(embed=em)
            session["POLLS"][numero] = {"MSGID" : msg.id,
                                             "QUESTION": question.capitalize(),
                                             "REPS": reps,
                                             "OPTS": {"souple": souple,
                                                      "nopin": nopin,
                                                      "mobile": mobile,
                                                      "notif": notif},
                                             "ACTIF": True,
                                             "EXPIRE": datedur,
                                             "AUTHOR_ID": ctx.message.author.id}
            for e in emos:
                try:
                    await self.bot.add_reaction(msg, e)
                except:
                    pass
            if mobile: await self.bot.add_reaction(msg, "📱")
            if nopin == False: await self.bot.pin_message(msg)

            while time.time() < maxdur and session["POLLS"][numero]["ACTIF"]:
                await asyncio.sleep(1)

            session["POLLS"][numero]["ACTIF"] = False
            upmsg = await self.bot.get_message(ctx.message.channel, session["POLLS"][numero]["MSGID"])
            if upmsg.pinned: await self.bot.unpin_message(upmsg)
            reptxt = statext = ""
            reps = self.get_reps(numero, server)
            total = sum([r.nb for r in reps])
            for r in reps:
                pourcent = r.nb / total if round(total) > 0 else 0
                reptxt += "\{} — **{}**\n".format(r.emoji, r.name)
                statext += "\{} — **{}** · {}%\n".format(r.emoji, r.nb, round(pourcent * 100, 1))
            em = discord.Embed(color=couleur)
            em.set_author(name="RÉSULTATS #{} — {}".format(numero, question.capitalize()),
                          icon_url=ctx.message.author.avatar_url)
            em.add_field(name="• Réponses", value= reptxt)
            em.add_field(name="• Stats", value= statext)
            votes = session["POLLS"][numero]["REPS"]
            total = sum([len(votes[i]["users"]) for i in votes])
            em.set_footer(text="Terminé — Merci d'y avoir participé | {} votes".format(total))
            await self.bot.say(embed=em)
            if recap:
                mlist = ""
                for r in reps:
                    mlist += "\n- {}\n".format(r.name)
                    mlist += "\n".join([server.get_member(u).name for u in r.users])
                txt = "• Réponses\n" + reptxt + "\n• Stats\n" + statext + "\n• Par membre\n" + mlist
                filename = "POLL_#{}.txt".format(numero)
                file = open("data/community/junk/{}".format(filename), "w", encoding="UTF-8")
                file.write(txt)
                file.close()
                try:
                    await self.bot.send_file(ctx.message.channel, "data/community/junk/{}".format(filename))
                    os.remove("data/community/junk/{}".format(filename))
                except Exception as e:
                    await self.bot.say("**Impossible d'upload le récapitualtif** — `{}`".format(e))
            del session["POLLS"][numero]
        else:
            txt = "**Format :** `{}sp Question ?; Réponse 1; Réponse 2; Réponse N [...]`\n\n**Remarques :**\n" \
                  "• Si aucune réponse n'est fournie, le poll se mettra automatiquement en sondage binaire OUI/NON.\n" \
                  "• Le vote expire après 5 minutes par défaut mais vous pouvez changer cette valeur en " \
                  "ajoutant l'option `-exp=Xm` avec X la valeur en minute à la fin de la commande.\n" \
                  "• L'option `-souple` permet de passer le poll en mode souple, c'est-à-dire qu'il permet la " \
                  "modification de son vote.\n" \
                  "• L'option `-nopin` indique au bot de ne pas épingler le sondage automatiquement. " \
                  "(Vous pourrez toujours le faire vous-même ou en réagissant avec l'emoji \📌)\n" \
                  "• `-notif` permet d'activer la réception d'un MP venant confirmer la participation au vote, " \
                  "pratique lorsqu'il faut prouver qu'un membre a voté.\n" \
                  "• `-recap` permet d'obtenir un fichier texte contenant un résumé complet des résultats à " \
                  "la fin du poll.\n" \
                  "• Enfin, `-mobile` ajoute une réaction sur le poll permettant de recevoir un affichage simplifié du " \
                  "poll adapté aux appareils ayant de petits écrans (< 5 pouces)".format(ctx.prefix)
            em = discord.Embed(title="Aide — Créer un poll", description=txt, color=0x43c8e0)
            await self.bot.say(embed=em)

    async def grab_reaction_add(self, reaction, user):
        message = reaction.message
        author = message.author
        server = message.server
        session = self.get_session(server)
        if not user.bot:
            if self.find_poll(message):
                poll, numero = self.find_poll(message)
                if reaction.emoji in [poll["REPS"][r]["emoji"] for r in poll["REPS"]]:
                    if not self.find_user_vote(numero, user):
                        for r in poll["REPS"]:
                            if reaction.emoji == poll["REPS"][r]["emoji"]:
                                poll["REPS"][r]["nb"] += 1
                                poll["REPS"][r]["users"].append(user.id)
                                await self.bot.edit_message(message, embed=self.gen_poll_embed(message))
                                if poll["OPTS"]["notif"]:
                                    await self.bot.send_message(user, "**POLL #{}** — Vote `{}` confirmé !".format(
                                        numero, r))
                                return
                    else:
                        await self.bot.remove_reaction(message, reaction.emoji, user)
                        if poll["OPTS"]["notif"]:
                            await self.bot.send_message(user, "**POLL #{}** — Vous avez déjà voté !".format(numero))
                elif reaction.emoji == "📱":
                    reptxt = statext = ""
                    reps = self.get_reps(numero, server)
                    total = sum([r.nb for r in reps])
                    for r in reps:
                        pourcent = r.nb / total if round(total) > 0 else 0
                        reptxt += "\{} — **{}**\n".format(r.emoji, r.name)
                        statext += "\{} — **{}** · {}%\n".format(r.emoji, r.nb, round(pourcent * 100, 1))
                    txt = "**POLL #{}** — ***{}***\n".format(numero, poll["QUESTION"])
                    txt += "• Réponses\n" + reptxt + "\n• Stats\n" + statext + "\n*Tu peux voter avec les réactions " \
                                                                               "en dessous du message sur le channel*"
                    await self.bot.send_message(user, txt)
                    await self.bot.remove_reaction(message, reaction.emoji, user)
                    try:
                        await self.bot.add_reaction(message, "📱")
                    except:
                        pass
                elif reaction.emoji == "📌":
                    if message.pinned == False:
                        if user.server_permissions.manage_messages:
                            await self.bot.pin_message(message)
                        else:
                            await self.bot.send_message(user, "**Action refusée** — Vous n'avez pas la permission"
                                                              " `manage_message`")
                    else:
                        await self.bot.send_message(user, "**Inutile** — Message déjà épinglé")
                    await self.bot.remove_reaction(message, reaction.emoji, user)
                else:
                    await self.bot.remove_reaction(message, reaction.emoji, user)

    async def grab_reaction_remove(self, reaction, user):
        message = reaction.message
        if self.find_poll(message):
            poll, numero = self.find_poll(message)
            if poll["OPTS"]["souple"]:
                if self.find_user_vote(numero, user):
                    for r in poll["REPS"]:
                        if reaction.emoji == poll["REPS"][r]["emoji"]:
                            if user.id in poll["REPS"][r]["users"]:
                                poll["REPS"][r]["nb"] -= 1
                                poll["REPS"][r]["users"].remove(user.id)
                                await self.bot.edit_message(message, embed=self.gen_poll_embed(message))
                                if poll["OPTS"]["notif"]:
                                    await self.bot.send_message(user, "**POLL #{}** — Vote `{}` retiré !".format(
                                        numero, r))
                                return

def check_folders():
    if not os.path.exists("data/community"):
        print("Création du dossier Community...")
        os.makedirs("data/community")
    if not os.path.exists("data/community/junk"):
        print("Création du dossier Community/Junk...")
        os.makedirs("data/community/junk")


def check_files():
    if not os.path.isfile("data/community/sys.json"):
        print("Création du fichier Community/sys.json...")
        fileIO("data/community/sys.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Community(bot)
    bot.add_cog(n)
    bot.add_listener(n.grab_reaction_add, "on_reaction_add")
    bot.add_listener(n.grab_reaction_remove, "on_reaction_remove")
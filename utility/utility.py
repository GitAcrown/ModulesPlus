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

DEFAULT_QUIT_LIST = ["{user.name} s'envole vers d'autres cieux.",
                     "L'agent n°{user.id} (a.k.a. *{user.name}*) a quitté notre monde.",
                     "{user.name} vient de quitter le serveur.",
                     "{user.name} a mystérieusement disparu de la liste des membres.",
                     "{user.name} est parti.",
                     "{user.name} est mort, tué par Covid-19.",
                     "{user.name} ~~a été suicidé de deux bans dans le dos~~ est parti.",
                     "{user.name} n'a pas survécu à cette communauté.",
                     "Plus besoin de bloquer {user.name}, il est parti tout seul !",
                     "Ce n'est qu'un au revoir {user.name}...",
                     "{user.name} n'a pas supporté l'odeur du serveur.",
                     "{server.name} se sépare en ce jour de {user.name}...",
                     "Ci-gît {user.name}, enième random ayant quitté le serveur.",
                     "{user.name} n'a pas survécu à la vague de bienveillance des membres de ce serveur.",
                     "{user.name} a préféré voir ailleurs.",
                     "{user.name} a roulé jusqu'en bas de la falaise, RIP.",
                     "{user.name} s'est noyé.",
                     "La mort est venue chercher {user.name}.",
                     "La vraie vie est venue chercher {user.name}.",
                     "{user.name} est parti, il préfère ses **vrais** amis."]


class Utility:
    """Outils communautaires avancés"""
    def __init__(self, bot):
        self.bot = bot
        self.sys = dataIO.load_json("data/utility/sys.json")
        self.cache = {}

    def get_server_cache(self, server, key):
        if server.id not in self.cache:
            self.cache[server.id] = {"poll": {}}
        return self.cache[server.id][key] if key else self.cache[server.id]

    def get_server_sys(self, server):
        if server.id not in self.sys:
            self.sys[server.id] = {"welcome": {"users": [],
                                               "joinmsg": "",
                                               "joinmsg_color": 0xE5E5E5,
                                               "quitmsg": False,
                                               "quitmsg_list": []}}
        return self.sys[server.id]

    def save_sys(self):
        fileIO("data/utility/sys.json", "save", self.sys)


    def _get_join_embed(self, server):
        sys = self.get_server_sys(server)["welcome"]
        if sys["joinmsg"]:
            em = discord.Embed(color=sys["joinmsg_color"], description=sys["joinmsg"])
            em.set_author(name="Message de " + server.name, icon_url=server.icon)
            return em
        return False

    @commands.group(name="welcome", pass_context=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def welcomeset(self, ctx):
        """Gestion des messages d'arrivées et de départ"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @welcomeset.command(pass_context=True)
    async def joinmsg(self, ctx, *texte):
        """Modifie le texte envoyé aux nouveaux membres

        Laisser [texte] vide pour désactiver cette fonctionnalité"""
        sys = self.get_server_sys(ctx.message.server)["welcome"]
        if texte:
            texte = " ".join(texte)
            texte = texte.replace(r"\n", "\n")
            self.get_server_sys(ctx.message.server)["welcome"]["joinmsg"] = texte
            await self.bot.say("**Notification d'arrivée modifiée avec succès** • Voici une prévisualisation...")
            em = self._get_join_embed(ctx.message.server)
            await self.bot.say(embed=em)
        else:
            self.get_server_sys(ctx.message.server)["welcome"]["joinmsg"] = ""
            await self.bot.say("**Notification d'arrivée désactivée**")
        self.save_sys()

    @welcomeset.command(pass_context=True)
    async def joinmsgcolor(self, ctx, couleur):
        """Modifie la couleur qu'on retrouve sur la notification d'arrivée du serveur"""
        await self.bot.say("Bientôt disponible.")

    @welcomeset.command(pass_context=True)
    async def joincache(self, ctx):
        """Vide le cache d'entrées

        Un cache enregistre tous les membres ayant déjà reçu le message d'arrivée afin d'empêcher qu'ils en recoivent un nouveau. Cette commande reset ce cache."""
        self.get_server_sys(ctx.message.server)["welcome"]["users"] = []
        self.save_sys()
        await self.bot.say("**Cache d'entrées vidé avec succès !**")

    @welcomeset.command(pass_context=True)
    async def quitmsg(self, ctx, channel: discord.Channel = None):
        """Active/Désactive l'affichage de notifications de départ sur le salon mentionné"""
        sys = self.get_server_sys(ctx.message.server)["welcome"]
        if channel:
            self.get_server_sys(ctx.message.server)["welcome"]["quitmsg"] = channel.id
            await self.bot.say("**Notifications de départ activées** • Elles s'afficheront sur {}".format(channel.mention))
        else:
            self.get_server_sys(ctx.message.server)["welcome"]["quitmsg"] = False
            await self.bot.say("**Notifications de départ désactivées**")
        self.save_sys()

    def _get_answers(self, server, num):
        polls = self.get_server_cache(server, "poll")
        if num in polls:
            objs = []
            answers = polls[num]["answers"]
            ans_list = [[r, answers[r]["count"], answers[r]["emoji"], answers[r]["voters"], answers[r]["index"]] for r in answers]
            ans_list = sorted(ans_list, key=operator.itemgetter(4))
            Answer = namedtuple('Answer', ['name', 'count', 'emoji', 'voters'])
            for r in ans_list:
                objs.append(Answer(r[0], r[1], r[2], r[3]))
            return objs

    def _find_poll(self, message):
        polls = self.get_server_cache(message.server, "poll")
        for poll in polls:
            if message.id == polls[poll]["message"].id:
                return polls[poll], poll
        return False

    def _find_voter(self, num, user):
        polls = self.get_server_cache(user.server, "poll")
        if num in polls:
            for a in polls[num]["answers"]:
                if user.id in polls[num]["answers"][a]["voters"]:
                    return a
        return False

    def _update_poll(self, message):
        if self._find_poll(message):
            poll, num = self._find_poll(message)
            base_em = message.embeds[0]
            ts_txt = poll["expire"]
            ans_txt = stats_txt = ""
            answers = self._get_answers(message.server, num)
            total = sum([a.count for a in answers])
            for a in answers:
                prc = a.count / total if round(total) > 0 else 0
                ans_txt += "\{} — **{}**\n".format(a.emoji, a.name)
                stats_txt += "\{} — ||**{}** · {}%||\n".format(a.emoji, a.count, round(prc * 100, 1))

            em = discord.Embed(color=base_em["color"])
            em.set_author(name=base_em["author"]["name"], icon_url=base_em["author"]["icon_url"])
            em.add_field(name="Réponses", value=ans_txt)
            em.add_field(name="Stats", value=stats_txt)
            em.set_footer(text="Votez avec les réactions ci-dessous | Expire {}".format(ts_txt))
            return em
        return False

    @commands.command(pass_context=True, aliases=["sondage"])
    async def reactpoll(self, ctx, *termes):
        """Démarre un sondage par réactions sur le salon de la commande

        <termes> = Question ?;Réponse 1;Réponse 2;Réponse N... + options éventuelles

        Options:
        -exp=X => Temps en minute au bout duquel le poll aura expiré (def.= 5m)
        -souple => Passe le sondage en mode souple (les votes peuvent être modifiés)
        -pin => Epingle/désépingle automatiquement le sondage
        -mobile => Ajoute la possibilité d'obtenir un affichage simplifié pour mobiles
        -confirm => Envoie un message de confirmation de vote ou de modification de vote en MP"""
        server = ctx.message.server
        polls = self.get_server_cache(server, "poll")

        letters_emojis = [s for s in "🇦🇧🇨🇩🇪🇫🇬🇭🇮🇯"]
        color = int("".join([random.choice(string.digits + "abcdef") for _ in range(6)]), 16)

        if termes:
            if termes[0].lower() == "stop" and int(termes[1]) in polls:
                poll = polls[int(termes[1])]
                try:
                    if poll[
                        "author"].id == ctx.message.author.id or ctx.message.author.server_permissions.manage_messages:
                        poll["on"] = False
                except:
                    await self.bot.say("**Permissions manquantes** — Vous devez être l'auteur du sondage ou "
                                       "avoir la permission `Gérer les messages` pour l'arrêter.")
                return

            if "?" in " ".join(termes):

                termes = " ".join(termes)
                souple = pin = mobile = confirm = recap = False
                exp = 5
                if "-" in termes:
                    r = re.compile(r'-exp=(\d+)', re.DOTALL | re.IGNORECASE).findall(termes)
                    if r:
                        r = r[0]
                        termes = termes.replace("-exp={}".format(r), "")
                        exp = int(r)
                    if "-souple" in termes:
                        termes = termes.replace("-souple", "")
                        souple = True
                    if "-pin" in termes:
                        termes = termes.replace("-pin", "")
                        pin = True
                    if "-mobile" in termes:
                        termes = termes.replace("-mobile", "")
                        mobile = True
                    if "-confirm" in termes:
                        termes = termes.replace("-confirm", "")
                        confirm = True
                if " ou " in termes and ";" not in termes:
                    qr = [termes] + [r.strip().capitalize() for r in termes.strip(" ?").split(" ou ")]
                    question = termes
                else:
                    qr = [r.strip().capitalize() for r in termes.strip(" ;").split(";")]
                    question = qr[0]
                end_timestamp = (datetime.now() + timedelta(minutes=int(exp)))
                if end_timestamp.date() > datetime.now().date():
                    ts_txt = end_timestamp.strftime("le %d/%m à %H:%M")
                else:
                    ts_txt = end_timestamp.strftime("à %H:%M")

                answers = {}
                emojis = []
                if len(qr) == 1:
                    answers = {"Oui": {"count": 0,
                                    "emoji": "👍",
                                    "voters": [],
                                    "index": 0},
                            "Non": {"count": 0,
                                    "emoji": "👎",
                                    "voters": [],
                                    "index": 1}}
                    ans_txt = "\👍 — **Oui**\n\👎 — **Non**"
                    stats_txt = "\👍 — ||**0** · 0%||\n\👎 — ||**0** · 0%||"
                    emojis = ["👍", "👎"]
                else:
                    ans_txt = stats_txt = ""
                    for i in [r.capitalize() for r in qr[1:]]:
                        index = qr[1:].index(i)
                        emoji = letters_emojis[qr[1:].index(i)]
                        answers[i] = {"count": 0,
                                      "emoji": emoji,
                                      "voters": [],
                                      "index": index}
                        ans_txt += "\{} — **{}**\n".format(emoji, i)
                        stats_txt += "\{} — ||**0** · 0%||\n".format(emoji)
                        emojis.append(emoji)

                num = sorted([p for p in polls], reverse=True)[0] + 1 if len(polls) > 1 else 1
                em = discord.Embed(color=color)
                em.set_author(name="#{} · {}".format(num, question.capitalize()), icon_url=ctx.message.author.avatar_url)
                em.add_field(name="Réponses", value=ans_txt)
                em.add_field(name="Stats", value=stats_txt)
                em.set_footer(text="Votez avec les réactions ci-dessous | Expire {}".format(ts_txt))
                msg = await self.bot.say(embed=em)
                polls[num] = {"message": msg,
                              "author": ctx.message.author,
                              "on": True,
                              "question": question,
                              "answers": answers,
                              "options": {"souple": souple,
                                          "pin": pin,
                                          "mobile": mobile,
                                          "confirm": confirm},
                              "expire": ts_txt}
                for e in emojis:
                    try:
                        await self.bot.add_reaction(msg, e)
                    except:
                        pass
                if mobile: await self.bot.add_reaction(msg, "📱")
                try:
                    if pin: await self.bot.pin_message(msg)
                except:
                    await self.bot.say("**Absence de permission :** `Impossible d'épingler automatiquement le sondage`")

                max_exp = end_timestamp.timestamp()
                while time.time() <= max_exp and polls[num]["on"]:
                    await asyncio.sleep(1)

                polls[num]["on"] = False
                up_msg = await self.bot.get_message(ctx.message.channel, polls[num]["message"].id)
                try:
                    if up_msg.pinned: await self.bot.unpin_message(up_msg)
                except:
                    await self.bot.say("**Absence de permission :** `Impossible de désépingler automatiquement le sondage`")
                ans_txt = stats_txt = ""
                answers = self._get_answers(server, num)
                total = sum([a.count for a in answers])
                for a in answers:
                    prc = a.count / total if round(total) > 0 else 0
                    ans_txt += "\{} — **{}**\n".format(a.emoji, a.name)
                    stats_txt += "\{} — **{}** · {}%\n".format(a.emoji, a.count, round(prc * 100, 1))

                em = discord.Embed(color=color)
                em.set_author(name="RÉSULTATS #{} · {}".format(num, question.capitalize()),
                              icon_url=ctx.message.author.avatar_url)
                em.add_field(name="Réponses", value=ans_txt)
                em.add_field(name="Stats", value=stats_txt)
                votes = polls[num]["answers"]
                total = sum([len(votes[v]["voters"]) for v in votes])
                em.set_footer(text="Sondage terminé — {} participants".format(total))
                await self.bot.say(embed=em)
                del polls[num]
            else:
                await self.bot.say("La question doit contenir un point d'interrogation")
        else:
            txt = "__**Format :**__ `{}sondage Question ?; Réponse 1; Réponse 2; Réponse N [...] + options`\n\n**Remarques :**\n" \
                  "• Si la question est binaire et qu'aucune réponse n'est fournie, le bot s'adaptera automatiquement.\n" \
                  "• Le vote expire après 5 minutes par défaut mais vous pouvez changer cette valeur en " \
                  "ajoutant l'option `-exp=X` avec X la valeur en minute à la fin de la commande.\n" \
                  "• L'option `-souple` permet de passer le poll en mode souple, c'est-à-dire qu'il permet la " \
                  "modification de son vote en annulant son ancienne réaction et en cliquant sur la nouvelle désirée.\n" \
                  "• L'option `-pin` indique au bot qu'il doit épingler le sondage (il le désépinglera tout seul à la fin). " \
                  "Notez que vous pouvez changer ce paramètre en réagissant sur le sondage avec l'emoji \📌\n" \
                  "• `-confirm` permet d'activer la réception d'un MP venant confirmer la participation au vote, " \
                  "pratique lorsqu'il faut prouver qu'un membre a voté.\n" \
                  "• Enfin, `-mobile` ajoute une réaction sur le poll permettant de recevoir un affichage simplifié du " \
                  "poll en MP adapté aux appareils ayant de petits écrans (< 5 pouces)".format(ctx.prefix)
            em = discord.Embed(title="Aide — Créer un poll", description=txt, color=0x43c8e0)
            await self.bot.say(embed=em)

    async def get_member_join(self, user):
        server = user.server
        if not user.bot:
            if self.get_server_sys(server)["welcome"]["joinmsg"]:
                sys = self.get_server_sys(server)["welcome"]
                em = self._get_join_embed(server)
                if user.id not in sys["users"]:
                    sys["users"].append(user.id)
                    try:
                        await self.bot.send_message(user, embed=em)
                    except:
                        pass

    async def get_member_quit(self, user):
        server = user.server
        if not user.bot:
            if self.get_server_sys(server)["welcome"]["quitmsg"]:
                sys = self.get_server_sys(server)["welcome"]
                channel = self.bot.get_channel(sys["quitmsg"])
                quit_txt = sys["quitmsg_list"] if sys["quitmsg_list"] else DEFAULT_QUIT_LIST
                quitmsg = random.choice(quit_txt)
                em = discord.Embed(color=user.color, description="\📢 " + quitmsg.format(user=user, server=server, channel=channel))
                await self.bot.send_message(channel, embed=em)

    async def get_reaction_add(self, reaction, user):
        message = reaction.message
        server = message.server
        if not user.bot:
            if self._find_poll(message):
                poll, num = self._find_poll(message)
                if reaction.emoji in [poll["answers"][a]["emoji"] for a in poll["answers"]]:
                    if not self._find_voter(num, user):
                        for a in poll["answers"]:
                            if reaction.emoji == poll["answers"][a]["emoji"]:
                                poll["answers"][a]["count"] += 1
                                poll["answers"][a]["voters"].append(user.id)
                                await self.bot.edit_message(message, embed=self._update_poll(message))
                                if poll["options"]["confirm"]:
                                    await self.bot.send_message(user, "**POLL #{}** — Vote `{}` confirmé le {} !".format(
                                        num, a, datetime.now().strftime("%d/%m/%Y à %H:%M")))
                                return
                    else:
                        await self.bot.remove_reaction(message, reaction.emoji, user)
                        if poll["options"]["confirm"]:
                            if poll["options"]["souple"]:
                                await self.bot.send_message(user, "**POLL #{}** — Vous avez déjà voté !\n"
                                                                  "Si vous voulez modifier votre vote, retirez d'abord votre ancien vote en recliquant sur la réaction puis choisissez une autre option.".format(num))
                            else:
                                await self.bot.send_message(user, "**POLL #{}** — Vous avez déjà voté !".format(num))
                elif reaction.emoji == "📱":
                    ans_txt = stats_txt = ""
                    answers = self._get_answers(message.server, num)
                    total = sum([a.count for a in answers])
                    for a in answers:
                        prc = a.count / total if round(total) > 0 else 0
                        ans_txt += "\{} — **{}**\n".format(a.emoji, a.name)
                        stats_txt += "\{} — ||**{}** · {}%||\n".format(a.emoji, a.count, round(prc * 100, 1))
                    txt = "**POLL #{}** — ***{}***\n".format(num, poll["question"])
                    txt += "• Réponses\n" + ans_txt + "\n• Stats\n" + stats_txt + "\n*Tu peux voter en cliquant sur " \
                                                                                  "les réactions correspondantes sous " \
                                                                                  "le sondage sur le serveur.*"
                    await self.bot.send_message(user, txt)
                    await self.bot.remove_reaction(message, reaction.emoji, user)
                    try:
                        await self.bot.add_reaction(message, "📱")
                    except:
                        pass
                elif reaction.emoji == "📌":
                    if not message.pinned:
                        if user.server_permissions.manage_messages:
                            await self.bot.pin_message(message)
                        else:
                            await self.bot.send_message(user, "**Action refusée** — Vous n'avez pas la permission"
                                                              " `Gérer les messages`")
                    else:
                        await self.bot.send_message(user, "**Inutile** — Message déjà épinglé")
                    await self.bot.remove_reaction(message, reaction.emoji, user)
                else:
                    await self.bot.remove_reaction(message, reaction.emoji, user)

    async def get_reaction_remove(self, reaction, user):
        message = reaction.message
        if self._find_poll(message):
            poll, num = self._find_poll(message)
            if poll["options"]["souple"]:
                if self._find_voter(num, user):
                    for a in poll["answers"]:
                        if reaction.emoji == poll["answers"][a]["emoji"]:
                            if user.id in poll["answers"][a]["voters"]:
                                poll["answers"][a]["count"] -= 1
                                poll["answers"][a]["voters"].remove(user.id)
                                await self.bot.edit_message(message, embed=self._update_poll(message))
                                if poll["options"]["confirm"]:
                                    await self.bot.send_message(user, "**POLL #{}** — Vote `{}` retiré !".format(
                                        num, a))
                                return


def check_folders():
    if not os.path.exists("data/utility"):
        print("Création du dossier utility...")
        os.makedirs("data/utility")


def check_files():
    if not os.path.isfile("data/utility/sys.json"):
        print("Création du fichier utility/sys.json...")
        fileIO("data/utility/sys.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Utility(bot)
    bot.add_cog(n)
    bot.add_listener(n.get_member_join, "on_member_join")
    bot.add_listener(n.get_reaction_add, "on_reaction_add")
    bot.add_listener(n.get_reaction_remove, "on_reaction_remove")
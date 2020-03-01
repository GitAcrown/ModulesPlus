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
from discord.ext import commands

from .utils.dataIO import fileIO, dataIO


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
                ans_txt = "\{} — **{}**\n".format(a.emoji, a.name)
                stats_txt = "\{} — ||**{}** · {}%||\n".format(a.emoji, a.count, round(prc * 100, 1))

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
            if "?" in " ".join(termes) and len(" ".join(termes).split("?")[1]) <= 11:
                if termes[0].lower() == "stop" and int(termes[1]) in polls:
                    poll = polls[int(termes[1])]
                    try:
                        if poll["author"].id == ctx.message.author.id or ctx.message.author.server_permissions.manage_messages:
                            poll["on"] = False
                    except:
                        await self.bot.say("**Permissions manquantes** — Vous devez être l'auteur du sondage ou "
                                           "avoir la permission `Gérer les messages` pour l'arrêter.")
                    return

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
                    ans_txt = "\{} — **{}**\n".format(a.emoji, a.name)
                    stats_txt = "\{} — **{}** · {}%\n".format(a.emoji, a.count, round(prc * 100, 1))

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
                await self.bot.say("La question doit contenir un point d'interrogation et il ne peut y avoir plus de "
                                   "10 éléments (réponses et options) après celui-ci.")
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
                        ans_txt = "\{} — **{}**\n".format(a.emoji, a.name)
                        stats_txt = "\{} — ||**{}** · {}%||\n".format(a.emoji, a.count, round(prc * 100, 1))
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
    bot.add_listener(n.get_reaction_add, "on_reaction_add")
    bot.add_listener(n.get_reaction_remove, "on_reaction_remove")
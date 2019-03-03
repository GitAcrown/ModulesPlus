import json
import os
import random
import time

import apiai
import discord
import praw
import wikipedia
import wikipediaapi
from google import google

from .utils.dataIO import fileIO, dataIO


class AwsmAPI:
    """API Awsm - Analyse du langage naturel"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.meta = {"last_save": 0}

    def save(self, force: bool = False):
        if force:
            fileIO("data/awsm/data.json", "save", self.data)
        elif (time.time() - self.meta["last_save"]) >= 30: # 30s
            fileIO("data/awsm/data.json", "save", self.data)
            self.meta["last_save"] = time.time()

class Awsm:
    """Assistant personnel embarqué - Pour vous servir"""
    def __init__(self, bot):
        self.bot = bot
        self.ctr = AwsmAPI(bot, "data/awsm/data.json")
        self.sys = dataIO.load_json("data/awsm/sys.json")
        self.metasys = {"ls": 0}
        self.context = {}
        # Reddit PRAW
        self.reddit = praw.Reddit(client_id='uE7NMd2ISBWR7w', client_secret='2pZk2tj9oHMMz_BJCzbJd4JrIRY',
                     user_agent='discordbot:Stayawsm.:1.0 (by /u/Nordsko)')
        # DialogFlow
        self.CLIENT_TOKEN = "448cd1b1db0c4ecfad775756ee521776"
        self.dialog = apiai.ApiAI(self.CLIENT_TOKEN)

    def redux(self, string: str, separateur: str = ".", limite: int = 2000):
        n = -1
        while len(separateur.join(string.split(separateur)[:n])) >= limite:
            n -= 1
        return separateur.join(string.split(separateur)[:n]) + separateur

    async def wikipedia(self, search: str, message: discord.Message):
        """Traite la demande de recherche Wikipedia"""
        langue = 'fr'
        wikipedia.set_lang(langue)
        wiki = wikipediaapi.Wikipedia(langue)
        while True:
            await self.bot.send_typing(message.channel)
            page = wiki.page(search)
            if page.exists():
                simil = wikipedia.search(search, 6, True)
                txtsimil = ""
                if simil:
                    if len(simil[0]) > 1:
                        txtsimil = "Résultats similaires • " + ", ".join(simil[0][1:])
                txt = self.redux(page.summary)
                if len(txt) == 1:
                    txt = "*Cliquez sur le titre pour accéder à la page d'homonymie*"
                em = discord.Embed(title=page.title, description=txt, color=0xeeeeee, url=page.fullurl)
                em.set_footer(text=txtsimil,
                              icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Wikipedia-"
                                       "logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png")
                msg = random.choice(["Voici ce que j'ai trouvé :", "Voilà :", "Voilà pour vous :", "Tout de suite :",
                                     "J'ai trouvé ça :"])
                await self.bot.send_message(message.channel, msg, embed=em)
                return True
            elif langue == 'en':
                wikipedia.set_lang('fr')
                search = wikipedia.search(search, 8, True)[0]
                if search:
                    ltxt = ""
                    liste = []
                    n = 1
                    for i in search:
                        liste.append([n, i])
                        n += 1
                    for _ in liste:
                        ltxt += "**{}** • {}\n".format(_[0], _[1].capitalize())
                    em = discord.Embed(title="Pages suggérées", description=ltxt, color=0xeeeeee)
                    msg = random.choice(["Je n'ai rien trouvé en particulier...",
                                         "Désolé mais je n'ai rien trouvé avec ce nom...",
                                         "Je ne peux que vous proposer des pages similaires.",
                                         "Je suis désolé mais je n'ai trouvé que ça :"])
                    rdfot = random.choice(
                        ["Que vouliez-vous exactement ?", "Quelle était votre recherche dans cette liste ?",
                         "Quel sujet est le bon ?", "Voulez-vous bien m'indiquer la bonne page à charger ?"])
                    em.set_footer(text=rdfot)
                    msg = await self.bot.send_message(message.channel, msg, embed=em)
                    rep = await self.bot.wait_for_message(channel=message.channel,
                                                          author=message.author,
                                                          timeout=10)
                    if rep is None:
                        await self.bot.delete_message(msg)
                        return True
                    elif rep.content.lower() in ["rien", "nvm", "nevermind", "stop", "merci",
                                                 "ca sera tout", "ça sera tout", "non merci"]:
                        poli = random.choice(["Bien entendu.", "D'accord, entendu.", "Très bien."])
                        await self.bot.send_message(message.channel, poli)
                        await self.bot.delete_message(msg)
                        return True
                    elif rep.content.lower() in [l.lower() for l in search]:
                        search = rep.content
                        await self.bot.delete_message(msg)
                    elif int(rep.content) in [i[0] for i in liste]:
                        search = False
                        for i in liste:
                            if int(rep.content) == i[0]:
                                search = i[1]
                                break
                        await self.bot.delete_message(msg)
                        if not search:
                            await self.bot.send_message(message.channel, "Aucun résulat.")
                            return
                    else:
                        await self.bot.delete_message(msg)
                        return True
                else:
                    wikipedia.set_lang('en')
                    search = wikipedia.search(search, 8, True)[0]
                    if search:
                        ltxt = ""
                        liste = []
                        n = 1
                        for i in search:
                            liste.append([n, i])
                            n += 1
                        for _ in liste:
                            ltxt += "**{}** • {}\n".format(_[0], _[1].capitalize())
                        em = discord.Embed(title="Pages suggérées (en Anglais)", description=ltxt, color=0xeeeeee)
                        msg = random.choice(["Je n'ai rien trouvé en particulier...",
                                             "Désolé mais je n'ai rien trouvé avec ce nom...",
                                             "Je ne peux que vous proposer des pages similaires.",
                                             "Je suis désolé mais je n'ai trouvé que ça :"])
                        rdfot = random.choice(
                            ["Que vouliez-vous exactement ?", "Quelle était votre recherche dans cette liste ?",
                             "Quel sujet est le bon ?",
                             "Voulez-vous bien m'indiquer la bonne page à charger ?"])
                        em.set_footer(text=rdfot)
                        msg = await self.bot.send_message(message.channel, msg, embed=em)
                        rep = await self.bot.wait_for_message(channel=message.channel,
                                                              author=message.author,
                                                              timeout=10)
                        if rep is None:
                            await self.bot.delete_message(msg)
                            return True
                        elif rep.content.lower() in ["rien", "nvm", "nevermind", "stop", "merci",
                                                     "ca sera tout", "ça sera tout", "non merci"]:
                            poli = random.choice(["Bien entendu.", "D'accord, entendu.", "Très bien."])
                            await self.bot.send_message(message.channel, poli)
                            await self.bot.delete_message(msg)
                            return True
                        elif rep.content.lower() in [l.lower() for l in search]:
                            search = rep.content
                            await self.bot.delete_message(msg)
                        elif int(rep.content) in [i[0] for i in liste]:
                            search = False
                            for i in liste:
                                if int(rep.content) == i[0]:
                                    search = i[1]
                                    break
                            await self.bot.delete_message(msg)
                            if not search:
                                await self.bot.send_message(message.channel, "Aucun résulat.")
                                return
                        else:
                            await self.bot.delete_message(msg)
                            return True
            else:
                langue = 'en'

    def reddit_sub(self, search: str):
        if "r/" in search:
            search = search.replace("r/", "")
        try:
            reddit = self.reddit.subreddits.search_by_name(search, exact=True)[0]
            if reddit.over18:
                txt = ""
                color = int('0x{}'.format(reddit.key_color[1:]), 16) if reddit.key_color else 0xfd4300
                for submit in reddit.hot(limit=3):
                    txt += "· ||**[{0}](https://www.reddit.com{1})**|| (u/[{2}](https://www.reddit.com/user/{2}))\n".format(
                        submit.title, submit.permalink, submit.author.name if submit.author else "???")
                em = discord.Embed(url="https://www.reddit.com/r/{}/".format(search),
                                   title="r/" + reddit.display_name.title() + " ─ Hot",
                                   description=txt, color=color)
                em.set_footer(text="Classé NSFW ─ Les titres sont cachés", icon_url="https://www.redditstatic.com/new-icon.png")
                return em
            else:
                txt = ""
                color = int('0x{}'.format(reddit.key_color[1:]), 16) if reddit.key_color else 0xfd4300
                for submit in reddit.hot(limit=3):
                    txt += "· **[{0}](https://www.reddit.com{1})** (u/[{2}](https://www.reddit.com/user/{2}))\n".format(
                        submit.title, submit.permalink, submit.author.name if submit.author else "???")
                em = discord.Embed(url="https://www.reddit.com/r/{}/".format(search),
                                   title="r/" + reddit.display_name.title() + " ─ Hot",
                                   description=txt, color=color)
                em.set_footer(text="Reddit", icon_url="https://www.redditstatic.com/new-icon.png")
                if reddit.banner_img:
                    em.set_image(url=reddit.banner_img)
                return em
        except Exception as e:
            print(e)
            return None

    def google(self, search):
        results = google.search(search, 1)
        txt = ""
        for i in results:
            name = i.name[:i.name.find("http")]
            txt += "· [{}]({})\n".format(name, i.link)
        if txt:
            em = discord.Embed(title="Recherche · " + search,color=0xF4B400, description=txt)
            em.set_footer(text="Google", icon_url="https://image.flaticon.com/teams/slug/google.jpg")
            return em
        return None

    async def on_msg(self, message: discord.Message):
        author = message.author
        self.bot_mention = "<@{}>".format(self.bot.user.id)
        if self.bot_mention in message.content:
            while True:
                content = message.content.replace(self.bot_mention, "")
                em = notif = None
                finish_after = False
                await self.bot.send_typing(message.channel)
                if content:
                    self.request = self.dialog.text_request()
                    self.request.session_id = str(author.id)
                    self.request.query = content
                    reponse = json.load(self.request.getresponse())
                    textrep = reponse["result"]["fulfillment"]["speech"]
                    type = str(reponse["result"]["metadata"]["intentName"]) if "intentName" in reponse["result"]["metadata"] else False
                    if type:
                        complete = not reponse["result"]["actionIncomplete"]
                        finish_after = True if "endConversation" in reponse["result"] else False
                        if complete:
                            if type == "search-general":
                                obj = reponse["result"]["parameters"]["obj"]
                                search_type = reponse["result"]["parameters"]["search_type"]
                                if search_type == "wikipedia":
                                    try:
                                        return await self.wikipedia(obj, message)
                                    except:
                                        textrep = "Désolé, je n'ai pas pu faire la recherche..."
                                elif search_type == "reddit":
                                    try:
                                        em = self.reddit_sub(obj)
                                        finish_after = True
                                    except:
                                        textrep = "Désolé, je n'ai rien trouvé..."

                    await self.bot.send_message(message.channel, textrep, embed=em)
                else:
                    deb = ["Que puis-je faire pour vous {} ?", "Que voulez-vous {} ?", "Puis-je vous servir {} ?"]
                    notif = await self.bot.send_message(message.channel, random.choice(deb).format(author.name))
                if not finish_after:
                    message = await self.bot.wait_for_message(channel=message.channel, author=message.author, timeout=7)
                    if not message:
                        if notif:
                            await self.bot.delete_message(notif)
                        return
                    else:
                        continue
                else:
                    return


def check_folders():
    if not os.path.exists("data/awsm"):
        print("Creation du fichier Awsm ...")
        os.makedirs("data/awsm")


def check_files():
    if not os.path.isfile("data/awsm/data.json"):
        print("Création de awsm/data.json ...")
        fileIO("data/awsm/data.json", "save", {})

    if not os.path.isfile("data/awsm/sys.json"):
        print("Création de awsm/sys.json ...")
        fileIO("data/awsm/sys.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Awsm(bot)
    bot.add_listener(n.on_msg, "on_message")
    bot.add_cog(n)

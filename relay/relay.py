import os
import re
import random
import asyncio
from collections import namedtuple

import discord
from __main__ import send_cmd_help
from discord.ext import commands

from .utils import checks
from .utils.dataIO import dataIO, fileIO


class RelayAPI:
    """API Relay - Système de communication de données inter-serveurs"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)
        self.channels = {"g": "global",
                         "fr": "français",
                         "en": "english"}

    def save(self):
        fileIO("data/relay/data.json", "save", self.data)

    def get_server(self, server: discord.Server, reset: bool=False):
        if server.id not in self.data["SERVERS"] or reset:
            r = lambda: random.randint(0, 255)
            color = int('0x%02X%02X%02X' % (r(), r(), r()), 16)
            self.data["SERVERS"][server.id] = {"CHANNELS": {"g": False,
                                                            "fr": False,
                                                            "en": False},
                                               "COLOR": color,
                                               "HIDE": [],
                                               "OPTS": {"autohide_bans": False,
                                                        "send_names": False}}
            self.save()
        return self.data["SERVERS"][server.id]

    def get_all_servers(self):
        total = {}
        for server in self.data["SERVERS"]:
            total[server] = {"SERVER": self.bot.get_server(server),
                             "CHANNELS": self.data["SERVERS"]["CHANNELS"],
                             "COLOR": self.data["SERVERS"]["COLOR"],
                             "HIDE": self.data["SERVERS"]["HIDE"]}
        return total

    def hidden(self, server: discord.Server, verif: list):
        bans = [user.id for user in self.bot.get_bans(server)]
        if server.id in self.data["SERVERS"]:
            for i in verif:
                if i in self.data["SERVERS"][server.id]["HIDE"] or i in bans:
                    return True
        return False

    def get_global(self):
        System = namedtuple('System', ['servers_bans', 'users_bans'])
        return System(self.data["GLOBAL"]["serverbans"], self.data["GLOBAL"]["userbans"])

    def load_channels(self):
        load = {}
        for c in self.channels:
            load[c] = []
            for s in self.data["SERVERS"]:
                if s not in self.data["GLOBAL"]["serverbans"]:
                    if c in self.data["SERVERS"][s]["CHANNELS"]:
                        chan = self.bot.get_channel(self.data["SERVERS"][s]["CHANNELS"][c])
                        if chan:
                            load[c].append(chan)
                        else:
                            self.data["SERVERS"][s]["CHANNELS"][c] = False
                    else:
                        self.data["SERVERS"][s]["CHANNELS"][c] = False
        self.save()
        return load if load else None

class Relay:
    """Système de communication inter-serveurs | Inter-servers communication system"""
    def __init__(self, bot):
        self.bot = bot
        self.api = RelayAPI(bot, "data/relay/data.json")
        self.load = self.api.load_channels()
        self.error_msg = {"disconnect": {"g": "Serveur déconnecté | Server disconnected",
                                         "fr": "Ce serveur s'est déconnecté.",
                                         "en": "This server has disconnected."},
                          "no_servers": {"g": "Aucun serveur connecté | Servers not found",
                                         "fr": "Aucun autre serveur n'est connecté à ce canal.",
                                         "en": "No server is connected to this channel."},
                          "not_send": {"g": "Erreur | Error",
                                       "fr": "**Erreur** ─ Votre message n'a pas été envoyé.",
                                       "en": "**Error** ─ Your message has not been sent."},
                          "connect": {"g": "Serveur connecté | Server connected",
                                      "fr": "Ce serveur vient de se connecter.",
                                      "en": "This server has just connected."}}

    def charge_dest(self, channel: discord.Message):
        for canal in self.load:
            if channel.id in [chan.id for chan in self.load[canal]]:
                loaded = [chan for chan in self.load[canal] if chan.id != channel.id]
                return loaded
        return None

    def find_dest(self, channel: discord.Message):
        for canal in self.load:
            if channel.id in [c.id for c in self.load[canal]]:
                return canal
        return None

    def is_connected(self, server: discord.Server):
        sys = self.api.get_server(server)
        liste = []
        for canal in sys["CHANNELS"]:
            if sys["CHANNELS"][canal]:
                liste.append([canal, self.bot.get_server(sys["CHANNELS"][canal])])
        return liste

    async def send_global_msg(self, title:str, content:str, channel: str = None):
        if channel:
            dest = self.load[channel]
        else:
            dest = []
            for c in self.load:
                for chan in self.load[c]:
                    dest.append(chan)
        em = discord.Embed(title=title, description=content, color=0xfd4c5e)
        em.set_footer(text="/{}/ ─ Relay β".format(channel if channel else "all"),
                      icon_url="https://i.imgur.com/ybbABbm.png")
        for chan in dest:
            try:
                await self.bot.send_message(chan, embed=em)
            except:
                pass

    @commands.group(name="relay", aliases=["rs"], pass_context=True, invoke_without_command=True, no_pm=True)
    async def _relay(self, ctx):
        """Gestion de la connexion au Relay | Relay connection management"""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.info)

    @_relay.commands(pass_context=True)
    async def info(self, ctx):
        """Informations à propos de votre connexion au Relay"""
        server = ctx.message.server
        connected = self.is_connected(server)
        if connected:
            txt = ""
            for e in connected:
                txt += "/**{}**/ ─ {}\n".format(e[0], e[1].mention)
            if len(connected) < 2:
                txt += "\n*Vous pouvez connecter d'autres canaux à l'aide de* `+rs channels`"
            em = discord.Embed(title="Canaux connectés", description=txt, color=0xfd4c5e)
            em.set_footer(text="Relay β", icon_url="https://i.imgur.com/ybbABbm.png")
            await self.bot.say(embed=em)
        else:
            em = discord.Embed(title="Canaux connectés",
                               description="**Aucun canal n'est connecté sur votre serveur.**\n"
                                           "Faîtes `+rs channels` pour en connecter.",
                               color=0xfd4c5e)
            em.set_footer(text="Relay β", icon_url="https://i.imgur.com/ybbABbm.png")
            await self.bot.say(embed=em)

    @_relay.commands(pass_context=True)
    @checks.admin_or_permissions(manage_channels=True)
    async def channels(self, ctx):
        """Gestion des canaux connectés"""
        server = ctx.message.server
        while True:
            sys = self.api.get_server(server)
            txt = ""
            for canal in sys["CHANNELS"]:
                if sys["CHANNELS"][canal]:
                    txt += "/**{}**/ ─ {}\n".format(canal, self.bot.get_channel(sys["CHANNELS"][canal].mention))
                else:
                    txt += "/**{}**/ ─ Non connecté\n".format(canal)
            em = discord.Embed(title="Canaux Relay connectés", description=txt, color=0xfd4c5e)
            em.set_footer(text="Relay β ─ Tapez le nom du canal pour changer son statut",
                          icon_url="https://i.imgur.com/ybbABbm.png")
            msg = await self.bot.say(embed=em)
            rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                  author=ctx.message.author,
                                                  timeout=20)
            if rep is None:
                await self.bot.delete_message(msg)
                return
            elif rep.content.lower() in [c for c in sys["CHANNELS"]]:
                canal = rep.content.lower()
                if sys["CHANNELS"][canal]:
                    await self.bot.delete_message(msg)
                    await self.bot.say("**Déconnexion...**")
                    await asyncio.sleep(1)
                    if ctx.message.channel.id != self.bot.get_channel(sys["CHANNELS"][canal].id):
                        await self.bot.send_message(self.bot.get_channel(sys["CHANNELS"][canal]),
                                                    "Ce channel à été déconnecté de /**{}**/.".format(canal))
                    sys["CHANNELS"][canal] = False
                    self.api.save()
                    self.load = self.api.load_channels()
                    await asyncio.sleep(0.75)
                    await self.bot.say("Votre serveur à été déconnecté de /**{}**/ avec succès.".format(canal))
                else:
                    await self.bot.delete_message(msg)
                    sup = await self.bot.say("**Mentionnez un channel sur lequel connecter /**{}**/ :**".format(canal))
                    conf = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                          author=ctx.message.author,
                                                          timeout=30)
                    if conf is None:
                        await self.bot.delete_message(sup)
                        return
                    elif len(conf.channel_mentions) == 1:
                        await self.bot.delete_message(sup)
                        await self.bot.say("**Connexion...**")
                        sys["CHANNELS"][canal] = conf.channel_mentions[0].id
                        self.api.save()
                        self.load = self.api.load_channels()
                        await asyncio.sleep(1.5)
                        txt = "Le réseau Relay permet aux membres de chaque serveur de discuter entre eux à travers ce bot. " \
                              "Tout membre ou serveur ne respectant pas les règles ci-dessous pourront se voir censurés de ce réseau.\n" \
                              "**1° Ne pas envoyer de nombreux messages dans un court laps de temps** comme le flood ou le spam, que ces messages aient un sens ou non.\n" \
                              "**2° Soyez sympas entre vous**, il est hors de question qu'il y ai des guerres entre les serveurs à travers ce réseau.\n" \
                              "**3° Ne pas abuser de la promotion de votre serveur**, ce n'est pas un espace publicitaire. Vous êtes autorisés à faire de la publicité pour votre serveur dans la limite du raisonnable (tant que ça ne dérange personne)."
                        em = discord.Embed(title="Charte du réseau Relay", description=txt, color=0xfd4c5e)
                        em.set_footer(text="Relay β", icon_url="https://i.imgur.com/ybbABbm.png")
                        await self.bot.send_message(conf.channel_mentions[0], embed=em)
                    else:
                        await self.bot.delete_message(sup)
                        await self.bot.say("**Invalide** ─ Vous devez seulement mentionner le salon que vous voulez "
                                           "relié au canal.")
            elif rep.content.lower() in ["quit", "stop"]:
                await self.bot.delete_message(msg)
                return
            else:
                await self.bot.say("**Invalide** ─ Ce canal n'existe pas.")

    @_relay.commands(pass_context=True)
    async def list(self, ctx):
        """Affiche des la liste des serveurs connectés"""
        txt = ""
        servs = self.api.get_all_servers()
        for serv in servs:
            salons = []
            for chan in servs[serv]["CHANNELS"]:
                if servs[serv]["CHANNELS"][chan]:
                    salons.append("**{}**/#{}".format(chan, self.bot.get_channel(servs[serv]["CHANNELS"][chan]).name))
            if servs[serv]["SERVER"].id == ctx.message.server.id:
                txt += "• __{} ({})__\n".format(servs[serv]["SERVER"].name, ", ".join(salons))
            else:
                txt += "• {} ({})\n".format(servs[serv]["SERVER"].name, ", ".join(salons))
        em = discord.Embed(title="Serveurs connectés au Relay", description=txt, color=0xfd4c5e)
        em.set_footer(text="Relay β", icon_url="https://i.imgur.com/ybbABbm.png")
        await self.bot.say(embed=em)

    @_relay.command(pass_context=True)
    @checks.admin_or_permissions(manage_channels=True)
    async def color(self, ctx, hex):
        """Change la couleur des membres de votre serveur sur le réseau Relay"""
        server = ctx.message.server
        sys = self.api.get_server(server)
        if "#" in hex:
            hex = hex[1:]
        elif "0x" in hex:
            hex = hex[2:]
        if hex == "000000":
            await self.bot.say("**Info** — #000000 est considéré comme la valeur par défaut par Discord et ne "
                               "s'affichera pas correctement.\nSi vous voulez du noir, utilisez #000001.")
        if len(hex) == 6:
            hex = int(hex, 16)
            sys["COLOR"] = hex
            em = discord.Embed(color=sys["COLOR"],
                               description="**Succès** — Voici une démonstration de la couleur choisie")
            em.set_footer(text="Besoin d'aide ? Allez sur http://www.color-hex.com/")
            await self.bot.say(embed=em)
            return
        await self.bot.say("**Erreur** — Impossible de changer la couleur")

    @_relay.command(pass_context=True)
    @checks.admin_or_permissions(manage_channels=True)
    async def reset(self, ctx):
        self.api.get_server(ctx.message.server, reset=True)
        await self.bot.say("**Reset effectué avec succès**")

    @_relay.command(pass_context=True)
    @checks.admin_or_permissions(manage_channels=True)
    async def extra(self, ctx):
        """Options supplémentaires annexes"""
        server = ctx.message.server
        msg = None
        while True:
            sys = self.api.get_server(server)
            txt = ""
            for opt in sys["OPTS"]:
                txt += "`{}` ─ *{}*\n".format(opt, "Activée" if sys["OPTS"][opt] else "Désactivée")
            em = discord.Embed(title="Options annexes du Relay", description=txt, color=0xfd4c5e)
            em.set_footer(text="Relay β ─ Tapez le nom de l'option pour activer/désactiver",
                          icon_url="https://i.imgur.com/ybbABbm.png")
            if msg:
                await self.bot.edit_message(msg, embed=em)
            else:
                msg = await self.bot.say(embed=em)
            rep = await self.bot.wait_for_message(channel=ctx.message.channel,
                                                  author=ctx.message.author,
                                                  timeout=20)
            if rep is None:
                await self.bot.delete_message(msg)
                return
            elif rep.content.lower() in [o for o in sys["OPTS"]]:
                sys["OPTS"][rep.content.lower()] = not sys["OPTS"][rep.content.lower()]
                self.api.save()
                em.set_footer(text="Relay β ─ Changement réalisé avec succès !",
                              icon_url="https://i.imgur.com/ybbABbm.png")
                await self.bot.edit_message(msg, embed=em)
                await asyncio.sleep(1.5)
                try:
                    await self.bot.delete_message(rep)
                except:
                    pass
            else:
                await self.bot.say("**Invalide** ─ Cette option n'existe pas")

    @_relay.command(pass_context=True)
    @checks.admin_or_permissions(manage_channels=True)
    async def hide(self, ctx, cible:str = None):
        """Permet de ne pas recevoir ou de recevoir à nouveau les messages d'un membre ou d'un serveur"""
        sys = self.api.get_server(ctx.message.server)
        if not cible:
            txt = ""
            servs = self.api.get_all_servers()
            for serv in servs:
                txt += "• {} ({})\n".format(servs[serv]["SERVER"].name, servs[serv]["SERVER"].id)
            txt += "\n*Pour avoir l'identifiant d'un membre, cliquez sur son pseudo sur un de ses messages Relay et" \
                   " regardez l'URL de la page.*"
            em = discord.Embed(title="Identifiants des serveurs connectés au Relay", description=txt, color=0xfd4c5e)
            em.set_footer(text="Relay β", icon_url="https://i.imgur.com/ybbABbm.png")
            await self.bot.say(embed=em)
        elif cible in sys["HIDE"]:
            sys["HIDE"].remove(cible)
            self.api.save()
            await self.bot.say("**Les messages de la cible ne seront plus cachés**")
        else:
            sys["HIDE"].append(cible)
            self.api.save()
            await self.bot.say("**Les messages de la cible seront désormais cachés**")

    async def transmit_msg(self, message: discord.Message):
        if message.author.id not in self.api.get_global().users_bans:
            if message.server.id not in self.api.get_global().servers_bans:
                if not message.content.startswith("+"):
                    dest = self.charge_dest(message.channel)
                    canal = self.find_dest(message.channel)
                    if dest:
                        sys = self.api.get_server(message.server)
                        thumbnail = image = None
                        content = message.content if message.content else ""
                        author_url = "https://discordapp.com/users/" + message.author.id
                        if message.embeds:
                            if "description" in message.embeds[0]:
                                content += "\n```" + message.embeds[0]["description"] + "```"
                            if "image" in message.embeds[0]:
                                thumbnail = message.embeds[0]["image"]["url"]
                        if message.attachments:
                            if [i for i in ["png", "jpeg", "jpg", "gif"] if i in message.attachments[0]["url"]]:
                                image = message.attachments[0]["url"]
                        if "http" in content:
                            reg = re.compile(r'(https?://(?:.*)/\w*\.[A-z]*)', re.DOTALL | re.IGNORECASE).findall(message.content)
                            image = reg[0] if reg[0] else image

                        em = discord.Embed(description=content, color=sys["COLOR"])
                        avatar = message.author.avatar_url if message.author.avatar_url else random.choice(["https://i.imgur.com/zg0DPMU.png",
                                                                                                            "https://i.imgur.com/u3ncV77.png",
                                                                                                            "https://i.imgur.com/vS6lIOR.png",
                                                                                                            "https://i.imgur.com/pNFXVgr.png"])
                        name = message.author.display_name
                        if sys["OPTS"].get("send_names", False):
                            name = message.author.name
                        em.set_author(name=name, icon_url=avatar)
                        em.set_footer(text="/{}/ ─ {}".format(canal, message.server.name))
                        if image:
                            em.set_image(url=image)
                        if thumbnail:
                            em.set_thumbnail(url=thumbnail)
                        for chan in dest:
                            if not self.api.hidden(chan.server, [message.server.id, message.author.id]):
                                try:
                                    await self.bot.send_message(chan, embed=em)
                                except:
                                    self.load = self.api.load_channels()
                                    await self.send_global_msg(chan.server.name, self.error_msg["disconnect"][canal], canal)
                    else:
                        await self.bot.send_message(message.channel, self.error_msg["no_servers"][canal])

    async def relay_msg(self, message):
        author = message.author
        if not author.bot:
            await self.transmit_msg(message)


def check_folders():
    if not os.path.exists("data/relay"):
        print("Creation du fichier relay ...")
        os.makedirs("data/relay")

def check_files():
    sys = {"SERVERS":{},
           "GLOBAL": {"userbans": [],
                      "serverbans": []}}
    if not os.path.isfile("data/relay/data.json"):
        print("Création de relay/data.json ...")
        fileIO("data/relay/data.json", "save", sys)

def setup(bot):
    check_folders()
    check_files()
    n = Relay(bot)
    bot.add_listener(n.relay_msg, "on_message")
    bot.add_cog(n)

import os
import re
import time
import random
import asyncio
from collections import namedtuple
from datetime import datetime, timedelta

import discord
from __main__ import send_cmd_help
from cogs.utils.chat_formatting import escape_mass_mentions
from discord.ext import commands

from .utils import checks
from .utils.dataIO import dataIO, fileIO


class RelayAPI:
    """API de Relay - Système de communication de données entre serveurs"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)

    def save(self):
        fileIO("data/relay/data.json", "save", self.data)

    def get_server(self, server: discord.Server, reset=False):
        if server.id not in self.data or reset:
            r = lambda: random.randint(0, 255)
            color = int('0x%02X%02X%02X' % (r(), r(), r()), 16)
            self.data[server.id] = {"CHANNEL": None,
                                    "GLOBALBAN": False,
                                    "BANLIST": [],
                                    "COLOR": color}
            self.save()
        return self.data[server.id]

    def get_all_servers(self):
        liste = []
        for serv in self.data:
            liste.append(serv)
        return liste

class Relay:
    """Système de communication de données entre serveurs"""
    def __init__(self, bot):
        self.bot = bot
        self.api = RelayAPI(bot, "data/relay/data.json")
        self.meta = {"CHANNELS": []}
        self.load_channels()

    def load_channels(self):
        """Charge le module Relay"""
        self.meta["CHANNELS"] = []
        channels = self.api.get_all_servers()
        for c in channels:
            self.meta["CHANNELS"].append(self.bot.get_channel(c))
        if len(self.meta["CHANNELS"]) > 0:
            return True # Signifiant Succès
        return False

    @commands.group(name="relayset", aliases=["rs"], pass_context=True)
    async def _relayset(self, ctx):
        """Gestion du réseau Relay"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_relayset.command(pass_context=True, hidden=True)
    async def reset(self, ctx):
        """Reset les paramètres du serveur en cours"""
        self.api.get_server(reset=True)
        await self.bot.say("**Reset effectué avec succès**")

    @_relayset.command(pass_context=True)
    async def color(self, ctx, hex):
        """Change la couleur des membres de votre serveur sur le réseau Relay"""
        server = ctx.message.server
        sys = self.api.get_server(server)
        if "#" in hex:
            col = hex[1:]
        elif "0x" in hex:
            hex = hex[2:]
        if hex == "000000":
            await self.bot.say("**Info**; — #000000 est considéré comme la valeur par défaut par Discord et ne "
                               "s'affichera pas correctement.\nSi vous voulez du noir, utilisez #000001.")
        if len(hex) == 6:
            hex = int(hex, 16)
            sys["COLOR"] = hex
            em = discord.Embed(color=sys["COLOR"],
                               description="**Succès** — Voici une démonstration de la couleur choisie")
            em.set_footer(text="Besoin d'aide ? Allez sur http://www.color-hex.com/")
            await self.bot.say(embed=em)
            return
        await self.bot.say("**Erreur** • Impossible de changer la couleur")

    @_relayset.command(pass_context=True)
    async def connect(self, ctx, channel: discord.Channel = None):
        """Se connecter au réseau Relay"""
        server = ctx.message.server
        sys = self.api.get_server(server)
        if not channel:
            for chan in server.channels:
                if chan.name.lower() in ["vcs", "relay", "irc"]:
                    channel = chan
        if sys["CHANNEL"]:
            await self.bot.say("**Déconnexion...**")
            sys["CHANNEL"] = False
            self.api.save()
            await asyncio.sleep(2)
            await self.bot.say("Votre serveur est désormais déconnecté du réseau **Relay**.")
        elif channel:
            await self.bot.say("**Connexion...**")
            sys["CHANNEL"] = channel.id
            self.api.save()
            txt = "Le réseau Relay permet aux membres de chaque serveur de discuter entre eux à travers ce bot. " \
                  "Tout membre ou serveur ne respectant pas les règles ci-dessous pourront se voir censurés de ce réseau.\n\n" \
                  "**1° Ne pas envoyer de nombreux messages dans un court laps de temps** comme le flood ou le spam, que ces messages aient un sens ou non.\n" \
                  "**2° Soyez sympas entre vous**, il est hors de question qu'il y ai des guerres entre les serveurs à travers ce réseau.\n" \
                  "**3° Ne pas abuser de la promotion de votre serveur**, ce n'est pas un espace publicitaire. Vous êtes autorisés à faire de la publicité pour votre serveur dans la limite du raisonnable (tant que ça ne dérange personne)."
            em = discord.Embed(title="Charte du réseau Relay", description=txt, color=0xFF7373)
            em.set_footer(text="Relay [ALPHA]", icon_url="https://i.imgur.com/PxAqP1C.png")
            await self.bot.send_message(channel, embed=em)
            self.load_channels()
            await self.bot.say("**Connecté sur** {}".format(channel.mention))
        else:
            await self.bot.say("**Erreur** • Vous n'avez défini aucun channel source\n"
                               "**Aide :** `.rs connect #channel` __ou__ nommez un salon `vcs`, ìrc` ou `relay`")

    async def relay_msg(self, message):
        server, channel = message.server, message.channel
        author = message.author
        if not author.bot:
            sys = self.api.get_server(server)
            if sys["CHANNEL"] == channel.id:
                em = discord.Embed(title=author.display_name, description=message.content, color=sys["COLOR"])
                await self.bot.delete_message(message)
                if self.meta["CHANNELS"]:
                    for chan in self.meta["CHANNELS"]:
                        await self.bot.send_message(chan, embed=em)
                else:
                    await self.bot.send_message(channel, "{} • Votre message n'a pas été envoyé".format(author.name))

def check_folders():
    if not os.path.exists("data/relay"):
        print("Creation du fichier relay ...")
        os.makedirs("data/relay")


def check_files():
    if not os.path.isfile("data/relay/data.json"):
        print("Création de relay/data.json ...")
        fileIO("data/relay/data.json", "save", {})


def setup(bot):
    check_folders()
    check_files()
    n = Relay(bot)
    bot.add_listener(n.relay_msg, "on_message")
    bot.add_cog(n)

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


class UsualAPI:
    """API Helper contenant diverses fonctionnalités pré-codées"""
    def __init__(self, bot, path):
        self.bot = bot
        self.data = dataIO.load_json(path)

    def check(self, reaction, user):
        return not user.bot

    async def pagify(self, ctx, title: str, texte: str, sep_algo: str = "PGNB", sep_symbol: str = ".", sep_limit: int = 2000):
        """Forme un Embed pagifié à partir d'un texte
        --- Algorithmes de découpage ---
        BRUT = Découpage au bout de sep_nb caractères (limite imposée par Discord)
        PGNB = Plus Grand Nombre de Blocs (un bloc = entre deux symboles de séparation)
        UNIQUE = Faire en sorte que chaque page corresponde à un bloc"""
        pages = []
        if sep_algo.upper() == "BRUT":
            while texte:
                pages.append(texte[:sep_limit])
                texte = texte[sep_limit:]
        elif sep_algo.upper() == "PGNB":
            if sep_symbol in texte:
                sep_limit -= len(sep_symbol)
                septxt = texte.split(sep_symbol)
                page = ""
                for s in septxt:
                    if len(page + s) < sep_limit:
                        page += s + sep_symbol
                    elif page:
                        pages.append(page)
                        page = ""
                    else:
                        return TimeoutError("La limite est inférieure à la longueur des blocs")
            else:
                return IndexError("Le symbole de découpage ne se trouve pas dans le texte.")
        elif sep_algo.upper() == "UNIQUE":
            pages = [s + sep_symbol for s in texte.split(sep_symbol)]
        else:
            return NameError("L'algorithme de découpage " + sep_algo.upper() + " n'existe pas.")

        actuel = 0
        msg = None
        while True:
            em = discord.Embed(title=title, description=pages[actuel])
            em.set_footer(text="─ Page n°{} sur {}".format(actuel, len(pages)))
            if not msg:
                msg = await self.bot.send_message(ctx.message.channel, embed=em)
            else:
                try:
                    await self.bot.clear_reactions(msg)
                except:
                    pass
                await self.bot.edit_message(msg, embed=em)
            emos = []
            if actuel > 0:
                await self.bot.add_reaction(msg, "⬅")
                emos.append("⬅")
            if actuel < len(pages):
                await self.bot.add_reaction(msg, "➡")
                emos.append("➡")
            if emos:
                await asyncio.sleep(0.2)
                rep = await self.bot.wait_for_reaction(["➡", "⬅"], message=msg, timeout=200, check=self.check)
                if rep is None:
                    await self.bot.delete_message(msg)
                    return
                elif rep.reaction.emoji == "➡":
                    actuel += 1 if actuel < len(pages) else 0
                elif rep.reaction.emoji == "⬅":
                    actuel -= 1 if actuel > 0 else 0
                else:
                    pass
            else:
                return

class Usual:
    """Démos de fonctionnalités Usual"""
    def __init__(self, bot):
        self.bot = bot
        self.usual = UsualAPI(bot, "data/usual/data.json")

    @commands.command(pass_context=True)
    async def pages(self, ctx, texte, limite: int = 500, sep_algo: str = "PGNB",  sep_symb: str = "."):
        """DEMO - Découpe un texte en pages
        Texte = texte à découper
        Limite = Nombre max. de caractères par page
        Sep_symb = Symbole de découpage des blocs en algo UNIQUE et PGNB
        Sep_algo = Algorithme de découpage (PNGB, BRUT, UNIQUE)"""
        await self.usual.pagify(ctx, "Texte découpé", texte, sep_algo, sep_symb, limite)

def check_folders():
    if not os.path.exists("data/usual"):
        print("Création du dossier usual ...")
        os.makedirs("data/usual")

def check_files():
    if not os.path.isfile("data/usual/data.json"):
        print("Création de usual/data.json ...")
        fileIO("data/usual/data.json", "save", {})

def setup(bot):
    check_folders()
    check_files()
    n = Usual(bot)
    bot.add_cog(n)
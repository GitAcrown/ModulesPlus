#  Roulette.py was created by Redjumpman for Redbot
#  This will create a rrgame.JSON file and a data folder
import asyncio
import os
import random
from time import strftime, localtime

import discord
from __main__ import send_cmd_help
from discord.ext import commands

from .utils import checks
from .utils.dataIO import dataIO

kill_message = ["Finalement {0} en avait dans la cervelle !",
                "Maintenant que {0} est parti·e on peut arrêter de jouer ! Non ? D'accord, très bien !",
                "NOOON. Pas {0} !",
                "Sa veste est à moi... Quoi, trop tôt ?",
                "Bien, je crois que {0} et moi ne pourront plus jouer à la roulette ensemble...",
                "Ci-gît {0}. Un gros nul.",
                "RIP {0}.",
                "J'aimais pas {0} de toute manière.",
                "Hey {0} ! Je suis revenu avec la bouffe ! Oh merde...",
                "Wow {0}, c'est presque de l'art moderne !",
                "Ah, je le savais !",
                "Sérieux ? C'est {0} qui est mort·e ? Ok, aucun suspens. Suivant.",
                "Est-ce que ça veut dire que je n'ai pas rendre le livre que {0} m'a prêté ?",
                "Mais merde à la fin ! Il y a le sang de {0} partout sur le salon !",
                "Je ne t'oublierai jamais {0}...",
                "Au moins {0} ne fera plus chier personne.",
                "Ne me regardez pas comme ça, c'est vous qui nettoyez le sang de {0}.",
                "Non je ne pleure pas, c'est vous qui pleurez. *snif*",
                "JE SAVAIS QUE TU POUVAIS LE FAIRE !",
                "Il y a sûrement quelqu'un qui l'aimait {0}. Peut-être.",
                "A jamais. {0}."
                "Génial. On se retrouve qu'avec les gens chiant.",
                "Je crois que j'en ai un peu sur moi. Dégueulasse.",
                "Je t'ai dis que fumer tue !",
                "Ahahah... C'était drôle putain...",
                "J'ai même pas eu le temps d'aller chercher le popcorn. Vous êtes méchant.",
                "Bordel, {0} a eu le temps de chier dans son froc avant de tirer.",
                "Mince, je n'avais pas prévu un trou aussi large...",
                "10/10 j'ai adoré voir {0} s'exploser le crâne, c'était GRANDIOSE.",
                "J'espère que {0} avait une assurance vie...",
                "Je ne sais pas comment, mais {1} a sûrement triché.",
                "{0} disait qu'il voulait avoir une mort digne. Loupé.",
                "Tun tun tun, *another one bites the dust*",
                "Bon arrête de pleurer {1}. {0} sait parfaitement ce qu'il fait c'est un PROFESSIONNEL.",
                "Donc c'est à ça vous ressemblez à l'intérieur !",
                "Mes condoléances {1}. Je sais que tu étais *très* proche de {0}.",
                "NON, DÎTES MOI QUE CE N'EST PAS VRAI ??? OSEF.",
                "Heure de mort {2}. Origine : la stupidité.",
                "BOOM HEADSHOT ! Désolé..."
                "Ne fais pas genre, tu as adoré {1} !",
                "MAIS-EUH, je voulais que ce soit {1} !",
                "Oh GE-NI-AL, {0} crève et on se retrouve avec {1}. Vraiment. Génial.",
                "Est-ce que tu manges ? T'as aucun respect {1} ! {0} vient de creuver !"]


class Russianroulette:
    """[2 à 6 joueurs] Jouer à la roulette russe"""

    def __init__(self, bot):
        self.bot = bot
        self.file_path = "data/roulette/russian.json"
        self.system = dataIO.load_json(self.file_path)
        self.version = "2.2.02"

    @commands.group(pass_context=True, no_pm=True)
    async def setroulette(self, ctx):
        """Paramètres de la roulette russe"""

        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setroulette.command(name="minbet", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _minbet_setroulette(self, ctx, bet: int):
        """Change l'offre minimale exigée pour jouer"""
        server = ctx.message.server
        settings = self.check_server_settings(server)
        if bet > 0:
            settings["System"]["Min Bet"] = bet
            dataIO.save_json(self.file_path, self.system)
            msg = "**Changée** ─ L'offre minimale est désormais {}".format(bet)
        else:
            msg = "**Erreur** ─ La valeur doit être supérieure à 0"
        await self.bot.say(msg)

    @setroulette.command(name="paycheck", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _pay_verify(self, ctx):
        """Vérifie que le système Iota Pay est connecté"""
        pay = self.bot.get_cog("Pay").pay
        try:
            pay.api_pong()
        except:
            await self.bot.say("**Erreur** ─ L'API Pay ne répond pas")
            return
        await self.bot.say("**Connectée** ─ L'API Pay répond correctement")

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_server=True)
    async def resetrr(self, ctx):
        """Reset le jeu si il est bloqué"""
        server = ctx.message.server
        settings = self.check_server_settings(server)
        self.reset_game(settings)
        await self.bot.say("**Reset** ─ Le jeu a été reset avec succès.")

    @commands.command(pass_context=True, no_pm=True, aliases=["rr", "roulette"])
    async def russian(self, ctx, offre: int):
        """Lance une partie de Roulette russe

        Attention : Léger flood du salon du jeu"""
        bet = offre
        user = ctx.message.author
        server = ctx.message.server
        settings = self.check_server_settings(server)
        pay = self.bot.get_cog("Pay").pay
        if await pay.verify(ctx):
            if await self.logic_checks(settings, user, bet):
                if settings["System"]["Roulette Initial"]:
                    if user.id in settings["Players"]:
                        msg = "**Déjà présent·e** | Tu es déjà dans la partie"
                    elif len(settings["Players"].keys()) >= 6:
                        msg = "**Maximum** | Le nombre maximal de joueurs est de 6"
                    else:
                        if bet == settings["System"]["Start Bet"]:
                            self.player_add(settings, user, bet)
                            self.subtract_credits(settings, user, bet)
                            msg = "**{}** ─ A rejoint la partie".format(user.name)
                        else:
                            start_bet = settings["System"]["Start Bet"]
                            money = pay.get_money(server, start_bet)
                            msg = "**Offre** | L'offre doit être égale à **{} {}**".format(start_bet, money)
                    await self.bot.say(msg)
                else:
                    self.initial_set(settings, bet)
                    self.player_add(settings, user, bet)
                    self.subtract_credits(settings, user, bet)
                    money = pay.get_money(server, bet)
                    txt = "{} à lancé une partie de Roulette avec une offre de départ de **{} {}**.".format(user.mention, bet,
                                                                                                        money)
                    em = discord.Embed(title="Roulette russe", description=txt, color=0x6b554e)
                    em.set_footer(text="Le jeu commence dans 45 secondes ou si 5 autres joueurs y participe. "
                                       "({}rr <offre>)".format(ctx.prefix))
                    await self.bot.say(embed=em)
                    await asyncio.sleep(45)
                    if len(settings["Players"].keys()) == 1:
                        seultxt = ["Désolé mais je ne vais pas vous laisser tirer une "
                                   "balle dans la tête sans personne pour y assister.",
                                   "La Roulette russe c'est plus fun à plusierus, là vous êtes seul·e.",
                                   "Non, je ne vais pas vous laisser vous suicider...",
                                   "Je suis sadique, mais pas au point de vous laisser mourir seul·e et sans amis.",
                                   "Personne ne vous a rejoint, on dirait qu'ils ne sont pas aussi fous que vous.",
                                   "Vous avez de la chance, on dirait que vous ne pouvez "
                                   "pas participer vu que vous êtes seul·e.",
                                   "Dommage que vous soyez seul·e, plus on est de fous plus on rit.",
                                   "J'étais pret mais apparemment vous êtes seul·e... inutile."]
                        await self.bot.say("**Seul·e...** | {}".format(random.choice(seultxt)))
                        player = list(settings["Players"].keys())[0]
                        mobj = server.get_member(player)
                        initial_bet = settings["Players"][player]["Bet"]
                        pay.depot_credits(mobj, initial_bet, "Remboursement partie vide (Roulette)")
                        self.reset_game(settings)
                    else:
                        settings["System"]["Active"] = True
                        m = None
                        etapes = ["Le jeu va pouvoir démarrer !",
                                  "Je vais mettre une balle dans ce **revolver**...",
                                  "...puis **le faire tourner** un coup...",
                                  "...et vous allez **vous le passer l'un après l'autre**...",
                                  "...jusqu'à que l'un de vous **s'explose la tête** !",
                                  "Le dernier en vie a gagné. **Bonne chance !**"]
                        for i in range(6):
                            if i + 1 < len(settings["Players"].keys()):
                                balles = "•" * (i + 1)
                            else:
                                balles = "•" * (len(settings["Players"].keys()))
                            em = discord.Embed(title="Préparation de la Roulette".format(user.name), description=etapes[i],
                                               color=0x6b554e)
                            em.set_footer(text=balles)
                            if not m:
                                m = await self.bot.say(embed=em)
                            else:
                                await self.bot.edit_message(m, embed=em)
                            await asyncio.sleep(2)
                        await asyncio.sleep(1)
                        await self.roulette_game(settings, server)
                        self.reset_game(settings)
        else:
            await self.bot.say("**Impossible** ─ Il te faut un comptre *Pay* valide pour y jouer.")

    async def logic_checks(self, settings, user, bet):
        if settings["System"]["Active"]:
            await self.bot.say("**En cours** | Attendez que la partie se termine avant d'en démarrer une autre.")
            return False
        elif bet < settings["System"]["Min Bet"]:
            min_bet = settings["System"]["Min Bet"]
            await self.bot.say("**Offre** | Votre offre doit être supérieure ou égale à {}.".format(min_bet))
            return False
        elif len(settings["Players"].keys()) >= 6:
            await self.bot.say("**Maximum de joueurs** | Trop de joueurs jouent actuellement.")
            return False
        elif not self.enough_credits(user, bet):
            await self.bot.say("**Banque** | Vous n'avez pas assez de crédit ou vous n'avez pas de compte.")
            return False
        else:
            return True

    async def roulette_game(self, settings, server):
        pot = settings["System"]["Pot"]
        turn = 0
        count = len(settings["Players"].keys())
        while count > 0:
            players = [server.get_member(x) for x in list(settings["Players"].keys())]
            if count > 1:
                count -= 1
                turn += 1
                await self.roulette_round(settings, server, players, turn)
            else:
                pay = self.bot.get_cog("Pay").pay
                winner = players[0]
                txt = "Bravo {}, tu es la dernière personne en vie.\n" \
                      "Tu gagnes **{} {}**.".format(winner.mention, pot, pay.get_money_name(server, pot))
                em = discord.Embed(title="Roulette russe ─ Gagnant", description=txt, color=0x6b554e)
                em.set_footer(text="{} {} ont été déposés sur le compte de {}".format(
                    pot, pay.get_money(server, pot), winner.name))
                await self.bot.say(embed=em)
                pay.gain_credits(winner, pot, "Gain Roulette")
                break

    async def roulette_round(self, settings, server, players, turn):
        roulette_circle = players[:]
        chamber = 6
        al = random.choice(["{} met une balle dans le barillet et donne un bon coup pour le faire tourner. "
                            "Avec un mouvement du poignet il le remet en place.",
                            "{} remet le révolver en ordre pour la prochaine manche...",
                            "{} donne un petit coup de chiffon sur le barillet avant de le charger "
                            "pour le tour suivant.",
                            "{} recharge le barillet et d'un coup sec le rebascule en place."])
        await self.bot.say("*{}*".format(al.format(self.bot.user.name)))
        await asyncio.sleep(3)
        await self.bot.say("**─── Round {} ───**".format(turn))
        while chamber >= 1:
            if not roulette_circle:
                roulette_circle = players[:]
            chance = random.randint(1, chamber)
            player = random.choice(roulette_circle)
            await self.bot.say("{} presse le révolver à sa tempe et appuie doucement sur la détente...".format(
                player.name))
            if chance == 1:
                await asyncio.sleep(4)
                msg = "**BANG** ─ **{}** est {}.".format(player.name, random.choice(["mort·e", "décédé·e", "kaputt",
                                                                                      "inanimé·e"]))
                await self.bot.say(msg)
                msg2 = random.choice(kill_message)
                settings["Players"].pop(player.id)
                remaining = [server.get_member(x) for x in list(settings["Players"].keys())]
                player2 = random.choice(remaining)
                death_time = strftime("%H:%M:%S", localtime())
                await asyncio.sleep(3)
                await self.bot.say(msg2.format(player.name, player2.name, death_time))
                await asyncio.sleep(3)
                break
            else:
                await asyncio.sleep(3)
                await self.bot.say("**CLIC** ─ **{}** a survécu·e.".format(player.name))
                await asyncio.sleep(3)
                roulette_circle.remove(player)
                chamber -= 1

    def reset_game(self, settings):
        settings["System"]["Pot"] = 0
        settings["System"]["Active"] = False
        settings["System"]["Start Bet"] = 0
        settings["System"]["Roulette Initial"] = False
        settings["Players"] = {}

    def player_add(self, settings, user, bet):
        settings["System"]["Pot"] += bet
        settings["Players"][user.id] = {"Name": user.name,
                                        "Mention": user.mention,
                                        "Bet": bet}

    def initial_set(self, settings, bet):
        settings["System"]["Start Bet"] = bet
        settings["System"]["Roulette Initial"] = True

    def subtract_credits(self, settings, user, bet):
        pay = self.bot.get_cog("Pay").pay
        pay.perte_credits(user, bet, "Offre Roulette")

    def enough_credits(self, user, amount):
        pay = self.bot.get_cog("Pay").pay
        if pay.get_account(user):
            if pay.enough_credits(user, amount):
                return True
            else:
                return False
        else:
            return False

    def check_server_settings(self, server):
        if server.id not in self.system["Servers"]:
            default = {"System": {"Pot": 0,
                                  "Active": False,
                                  "Start Bet": 0,
                                  "Roulette Initial": False,
                                  "Min Bet": 50},
                       "Players": {}
                       }
            self.system["Servers"][server.id] = default
            dataIO.save_json(self.file_path, self.system)
            print("Création des paramètres par défaut de la Roulette pour le serveur : {}".format(server.name))
            path = self.system["Servers"][server.id]
            return path
        else:
            path = self.system["Servers"][server.id]
            return path


def check_folders():
    if not os.path.exists("data/roulette"):
        print("Création de Roulette...")
        os.makedirs("data/roulette")


def check_files():
    system = {"Servers": {}}

    f = "data/roulette/russian.json"
    if not dataIO.is_valid_json(f):
        print("Création fichier roulette...")
        dataIO.save_json(f, system)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(Russianroulette(bot))
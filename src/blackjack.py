from enum import Enum, auto
from typing import Tuple
from collections import deque
from itertools import product, starmap
from random import shuffle, randint
from abc import ABC, abstractmethod
import matplotlib.pyplot as plt
import numpy as np

class Card:

	Suit = Enum('Suit', "Diamonds Clubs Hearts Spades")
	Value = Enum('Value', " ".join([str(i) for i in range(2, 11)] + ['J', 'Q', 'K', 'A']))

	def __init__(self, value: Value, suit: Suit):
		self.value = value
		self.suit = suit
	
	def __str__(self):
		return self.value.name + ' of ' + self.suit.name
	
	def __repr__(self):
		return str(self)

class Deck:

	def __init__(self):
		self.cards = deque(starmap(Card, product(Card.Value, Card.Suit)))
		
	def shuffle(self):
		shuffle(self.cards)

	def draw(self):
		return self.cards.popleft()

	def __str__(self):
		return str(self.cards)
	
	def __len__(self):
		return len(self.cards)

class Hand:

	class State(Enum):

		# OPEN = resolved & cards are shown
		OPEN = auto(),
		CLOSED = auto()
	
	def __init__(self):
		self.cards: list[Card] = []
		self.state = self.State.CLOSED

	def draw_one(self, deck: Deck):
		self.cards.append(deck.draw())
	
	def clear(self):
		self.cards = []
		self.state = self.State.CLOSED
	
	def __str__(self):
		return str(self.cards)
	
	def __len__(self):
		return len(self.cards)

class GameRuleset(ABC):

	@abstractmethod
	def hand_value(self, hand: Hand) -> int:
		pass

	@abstractmethod
	def payout_multiplier(self, hand: Hand):
		pass

class GamePlayer(ABC):

	def __init__(self):
		self.hand = Hand()
		self.bust = False
		self.ruleset = None
	
	def inject_ruleset(self, ruleset: GameRuleset):
		self.ruleset = ruleset
	
	@abstractmethod
	def decide(self):
		pass

class BettingStrategy(ABC):

	def __init__(self):
		super().__init__()

	@abstractmethod
	def place_bet(self, bankroll: int, history: Tuple[str, list[Card], int, int]) -> int:
		pass

class PlayerHistory():

	def __init__(self, win: bool, hand: Hand, bet: int, new_bankroll: int, profit: int):
		self.win = win
		self.hand = hand
		self.bet = bet
		self.new_bankroll = new_bankroll
		self.profit = profit

	def __str__(self):
		print(f"(Player win: {self.win}, Hand: {self.hand}, Bet: {self.bet}, Bankroll: {self.new_bankroll}, Profit: {self.profit})")

	def __repr__(self):
		return str(self)

class DealerHistory():

	def __init__(self, hand: Hand, no_win: int, no_lose: int, no_draw: int, new_bankroll: int, profit: int):
		self.hand = hand
		self.round_wins = no_win
		self.round_losses = no_lose
		self.round_draws = no_draw
		self.new_bankroll = new_bankroll
		self.profit = profit
	
	def __str__(self):
		print(f"(Banker Hand: {self.hand}, {self.round_wins} wins, {self.round_losses} losses, {self.round_draws} draws, Bankroll: {self.new_bankroll}, Profit: {self.profit})")
	
	def __repr__(self):
		return str(self)
class PlayerStrategy(ABC):

	def __init__(self, ruleset: GameRuleset):
		super().__init__()
		self.ruleset = ruleset
	
	@abstractmethod
	def determine_action(self, hand: Hand, history: list[PlayerHistory]) -> 'Player.Action':
		pass

class DealerStrategy(ABC):
	
	def __init__(self, ruleset: GameRuleset):
		super().__init__()
		self.ruleset = ruleset

	@abstractmethod
	def determine_action(self, hand: Hand, history: list[DealerHistory], player_info: Tuple[Hand.State, Hand | int]) -> Tuple['Dealer.Action.RESOLVE', int] | Tuple['Dealer.Action.HIT', None]:
		pass


class Player(GamePlayer):

	class Action(Enum):

		RUN = auto(),
		HIT = auto(),
		STAND = auto()

	def __init__(self, iden, initial_bankroll: int, betting_strat: BettingStrategy, player_strat: PlayerStrategy):
		super().__init__()
		self.iden = iden
		self.bankroll = initial_bankroll
		self.games_played = 0
		self.curr_bet = 0
		self.history = [] # (is_win: bool, hand: Hand, bet: int, new_bankroll: int)
		self.betting_strat = betting_strat
		self.player_strat = player_strat
	
	def reset(self):
		self.hand.clear()
		self.bust = False
	
	def get_curr_hand_info(self) -> Tuple[Hand.State, Hand | int]:
		if self.hand.state is self.hand.State.OPEN:
			return (self.hand.state, self.hand)
		return (self.hand.state, len(self.hand.cards))

	def decide(self) -> 'Player.Action':
		return self.player_strat.determine_action(self.hand, self.history)

	def bet(self):
		self.curr_bet = self.betting_strat.place_bet(self.bankroll, self.history)

	def action(self, action: 'Player.Action', deck: Deck):

		if action is Player.Action.RUN:
			self.hand.state = Hand.State.OPEN
			self.history.append(PlayerHistory(None, self.hand, self.curr_bet, self.bankroll, 0))

			# print(f"[Player {self.iden}] RUN")
		
		elif action is Player.Action.HIT:
			self.hand.draw_one(deck)
			# print(f"[Player {self.iden}] {action.name} -> {self.hand.cards[-1]}")
			if self.ruleset.hand_value(self.hand) > 21:
				self.bust = True
				# print(f"[Player {self.iden}] BUST")
		
		else:
			# print(f"[Player {self.iden}] STAND")
			pass

class Dealer(GamePlayer):

	class Action(Enum):

		HIT = auto(),
		RESOLVE = auto()

	def __init__(self, initial_bankroll: int, dealer_strat: DealerStrategy):
		super().__init__()
		self.bankroll = initial_bankroll
		self.games_played = 0
		self.dealer_strat = dealer_strat
		self.round_wins = 0
		self.round_losses = 0
		self.round_draws = 0
		self.round_profit = 0
		self.history = []

	def reset(self):
		self.hand.clear()
		self.wins = 0
		self.losses = 0
		self.draws = 0
		self.round_profit = 0
		self.bust = False

	def decide(self, player_info: Tuple[Hand.State, Hand | int]) -> Tuple['Dealer.Action.RESOLVE', int] | 'Dealer.Action.HIT':
		return self.dealer_strat.determine_action(self.hand, self.history, player_info)

	def action(self, action: 'Dealer.Action', target_player: Player, deck: Deck):

		if action is Dealer.Action.HIT:
			self.hand.draw_one(deck)
			if self.ruleset.hand_value(self.hand) > 21:
				self.bust = True
			# print(f"[Dealer]: {action.name} -> {self.hand.cards[-1]}")

		if action is Dealer.Action.RESOLVE:

			dealer_hand_value = self.ruleset.hand_value(self.hand)
			player_hand_value = self.ruleset.hand_value(target_player.hand)

			dealer_win = None

			winnings = 0

			if (dealer_hand_value > player_hand_value and dealer.bust is False) or (target_player.bust is True and dealer.bust is False): # dealer win
				
				payout_mult = self.ruleset.payout_multiplier(self.hand)
				winnings = payout_mult * target_player.curr_bet
				self.bankroll += winnings
				target_player.bankroll -= winnings
				dealer_win = True
				self.round_profit += winnings
				self.round_wins += 1
				
			elif (player_hand_value > dealer_hand_value and target_player.bust is False) or (dealer.bust is True and target_player.bust is False): # player win
				payout_mult = self.ruleset.payout_multiplier(target_player.hand)
				winnings = payout_mult * target_player.curr_bet
				self.bankroll -= winnings
				target_player.bankroll += winnings
				dealer_win = False
				self.round_losses += 1
				self.round_profit -= winnings
			else: # else push
				self.round_draws += 1

		
			# print(f"[Dealer] {action.name} -> {dealer.hand} ({dealer_hand_value}) vs {target_player.hand} ({player_hand_value}) = {"DRAW" if dealer_win is None else "LOSE" if dealer_win is False else "WIN"}")
			
			target_player.history.append(PlayerHistory(not dealer_win, target_player.hand, target_player.curr_bet, target_player.bankroll, winnings * (-1 if dealer_win else 1)))
			target_player.hand.state = Hand.State.OPEN

class Game:

	def __init__(self, dealer: Dealer, players: list[Player], ruleset: GameRuleset):
		
		self.dealer = dealer
		self.players = players
		self.ruleset = ruleset
		self.deck = Deck()
		self.deck.shuffle()

		for player in self.players:
			player.inject_ruleset(ruleset)
		self.dealer.inject_ruleset(ruleset)

	def play(self):

		for p in self.players:
			p.games_played += 1
		self.dealer.games_played += 1

		self._player_bets()
		self._deal_hands()
		self._player_turn()
		self._dealer_turn()
		self._clear()

	def _player_bets(self):
		for p in self.players:
			p.bet()

	def _deal_hands(self):

		# each player draws 2
		for _ in range(2):
			for p in self.players:
				p.hand.draw_one(self.deck)
			self.dealer.hand.draw_one(self.deck)
	
	def _player_turn(self):

		for p in range(len(self.players)):
			player_action = None
			while player_action not in [Player.Action.STAND, Player.Action.RUN]:
				player_action = self.players[p].decide()
				self.players[p].action(player_action, self.deck)

	def _dealer_turn(self):

		players_hand_info = [p.get_curr_hand_info() for p in self.players]

		# dealers turn until all players have been resolved
		while any((lambda x: x[0] == Hand.State.CLOSED)(info) for info in players_hand_info):
			
			dealer_action, target_p = self.dealer.decide(players_hand_info)
			target_player = None
			if target_p is not None:
				target_player = self.players[target_p]
			
			self.dealer.action(dealer_action, target_player, self.deck)
			players_hand_info = [p.get_curr_hand_info() for p in self.players]
		
		dealer.history.append(DealerHistory(dealer.hand, dealer.round_wins, dealer.round_losses, dealer.round_draws, dealer.bankroll, dealer.round_profit))

	def _clear(self):
		for p in self.players:
			p.reset()
		self.dealer.reset()

class Session:

	def __init__(self, no_games: int, game_ruleset: GameRuleset, players: list[Player], dealer: Dealer):
		self.no_games = no_games
		self.games_played = 0
		self.players = players
		self.dealer = dealer
		self.game_ruleset = game_ruleset

	def simulate(self):
		
		for i in range(self.no_games):
			# print(f"Game {i}")
			game = Game(self.dealer, self.players, self.game_ruleset)
			game.play()
			self.games_played += 1

			# players drop out if bankroll goes negative
			self.players = [p for p in self.players if p.bankroll > 0]

			# dealer drops out if bankroll goes negative, session ends
			if self.dealer.bankroll < 0:
				return

# --- Implementation

class RandomBettingStrategy(BettingStrategy):

	def __init__(self, a: int, b: int):
		super().__init__()
		self.a = a
		self.b = b

	def place_bet(self, bankroll: int, history: Tuple[str, list[Card], int, int]) -> int:
		return min(bankroll, randint(self.a, self.b))

class FlatBettingStrategy(BettingStrategy):

	def __init__(self, flat_bet: int):
		super().__init__()
		self.flat_bet = flat_bet
	
	def place_bet(self, bankroll: int, history: Tuple[str, list[Card], int, int]) -> int:
		return min(bankroll, self.flat_bet)

class RegularPlayerStrategy(PlayerStrategy):

	def determine_action(self, hand: Hand, history: list[Tuple[bool, Hand, int, int]]) -> 'Player.Action':
		
		if self.ruleset.hand_value(hand) == 15 and len(hand) == 2:
			return Player.Action.RUN

		if self.ruleset.hand_value(hand) < 16:
			return Player.Action.HIT

		return Player.Action.STAND

class RegularDealerStrategy(DealerStrategy):

	def determine_action(self, hand: Hand, history: list[Tuple[Hand, int, int, int]], player_info: Tuple[Hand.State, Hand | int]) -> Tuple['Dealer.Action.RESOLVE', int] | Tuple['Dealer.Action.HIT', None]:
		
		if self.ruleset.hand_value(hand) < 16:
			return Dealer.Action.HIT, None

		for i in range(len(player_info)):
			if player_info[i][0] == Hand.State.CLOSED:
				return Dealer.Action.RESOLVE, i

class ChineseBlackjackRuleset(GameRuleset):
	
	def hand_value(self, hand: Hand):

		value = 0
		for card in hand.cards:

			if card.value.name in ['J', 'Q', 'K']:
				value += 10
			elif card.value.name == 'A':
				if len(hand) <= 2:
					value += 11
				elif len(hand) == 3:
					value += 10 if (value + 10) < 21 else 1
				elif len(hand) > 3:
					value += 1
			else:
				value += int(card.value.name)

		return value

	def payout_multiplier(self, hand):

		if len(hand) == 5:

			if self.hand_value(hand) == 21:
				return 3

			return 2
		
		if self.hand_value(hand) == 21:

			if len(hand) == 2 and \
				all(hand.cards[i].value == Card.Value.A for i in range(len(hand))):
				return 3

			return 2

		if len(hand) == 2 and hand.cards[0].value == hand.cards[1].value and \
			hand.cards[0].value in ['8', '9', '10', 'J', 'Q', 'K']:
			return 2

		return 1

if __name__ == "__main__":
	from math import inf
	
	rand_bs = RandomBettingStrategy(1, 2)
	flat_bs = FlatBettingStrategy(1)
	chinese_ruleset = ChineseBlackjackRuleset()
	ps = RegularPlayerStrategy(chinese_ruleset)
	ds = RegularDealerStrategy(chinese_ruleset)
	
	TOTAL_GAMES = 100000

	dealer_evs = []

	for player_count in range(1, 16):

		print(f"Player count: {player_count}")

		players = [Player(i + 1, inf, flat_bs, ps) for i in range(player_count)]
		dealer = Dealer(inf, ds)

		s = Session(TOTAL_GAMES, chinese_ruleset, players, dealer)
		s.simulate()

		x = np.linspace(0, s.games_played, num=s.games_played)
		ys = []
		for p in players:
			y = [h.profit for h in p.history]
			print(f"Expected value for player {p.iden}: {np.mean(y)}")
			if len(y) < s.games_played:
				y += [y[-1]] * (s.games_played - len(y))
			ys.append(y)

		# print(ys)

		yd = [h.profit for h in dealer.history]
		dealer_evs.append(np.mean(yd))
		print(f"Expected value for dealer: {np.mean(yd)}")

	plt.plot(np.linspace(1, 15, 15), dealer_evs)

	# print(yd)

	# for i, y in enumerate(ys):
	# 	plt.plot(x, y, label=f'Player {i + 1}')
	# plt.plot(x, yd, label='Dealer')

	# plt.legend()
	plt.show()
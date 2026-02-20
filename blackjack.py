from enum import Enum, auto
from collections import deque
from itertools import product, starmap
from random import shuffle
from abc import ABC, abstractmethod

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
		self.cards = []
		self.state = self.State.CLOSED

	def draw_one(self, deck: Deck):
		self.cards.append(deck.draw())

class GameRuleset(ABC):

	@abstractmethod
	def hand_value(self, hand: Hand) -> int:
		pass

	@abstractmethod
	def payout_multiplier(self, hand_a: Hand, hand_b: Hand):
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
	def place_bet(self, history: tuple[str, list[Card], int, int]) -> int:
		pass

class PlayerStrategy(ABC):

	def __init__(self):
		super().__init__()
	
	@abstractmethod
	def determine_action(hand: Hand, history: list[tuple[bool, Hand, int, int]]) -> 'Player.Action':
		pass

class DealerStrategy(ABC):
	
	def __init__(self):
		super().__init__()

	@abstractmethod
	def determine_action(hand: Hand, history: list[tuple[Hand, int, int, int]]) -> tuple['Dealer.Action.RESOLVE', int] | 'Dealer.Action.HIT':
		pass

class Player(GamePlayer):

	class Action(Enum):

		HIT = auto(),
		STAND = auto()

	def __init__(self, initial_bankroll: int, betting_strat: BettingStrategy, player_strat: PlayerStrategy):
		super().__init__()
		self.bankroll = initial_bankroll
		self.curr_bet = 0
		self.history = [] # (is_win: bool, hand: Hand, bet: int, new_bankroll: int)
		self.betting_strat = betting_strat
		self.player_strat = player_strat
	
	def get_curr_hand_info(self):
		if self.hand.state is self.hand.State.OPEN:
			return (self.hand.state, self.hand)
		return (self.hand.state, len(self.hand.cards))

	def decide(self) -> 'Player.Action':
		return self.game_strat.determine_action(self.hand, self.history)

	def bet(self):
		self.curr_bet = self.betting_strat.place_bet(self.history)

	def action(self, action: 'Player.Action', deck: Deck):

		if action is Player.Action.HIT:
			self.hand.draw_one(deck)
			if self.ruleset.hand_value() > 21:
				self.bust = True

class Dealer(GamePlayer):

	class Action(Enum):

		HIT = auto(),
		RESOLVE = auto()

	def __init__(self, initial_bankroll: int, dealer_strat: DealerStrategy):
		super().__init__()
		self.bankroll = initial_bankroll
		self.dealer_strat = dealer_strat
		self.history = [] # (hand: Hand, no_win: int, no_lose: int, new_bankroll: int)

	def decide(self, player_info) -> tuple['Dealer.Action.RESOLVE', int] | 'Dealer.Action.HIT':
		self.dealer_strat.determine_action(self.hand, self.history, player_info)

	def action(self, action: 'Dealer.Action', target_player: Player, deck: Deck):

		if action is Dealer.Action.HIT:
			self.hand.draw_one(deck)
			if self.ruleset.hand_value() > 21:
				self.bust = True
		if action is Dealer.Action.RESOLVE:

			pass

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

		self._player_bets()
		self._deal_hands()
		self._player_turn()
		self._dealer_turn()

	def _player_bets(self):
		for p in self.players:
			p.bet()

	def _deal_hands(self):

		# each player draws 2
		for _ in range(2):
			for p in self.players:
				p.draw_one(self.deck)
			self.dealer.draw_one(self.deck)
	
	def _player_turn(self):

		for p in range(len(self.players)):
			player_action = None
			while player_action is not Player.Action.STAND:
				player_action = self.players[p].decide()
				self.players[p].action(player_action, self.deck)

	def _dealer_turn(self):

		players_hand_info = [p.get_curr_hand_info() for p in self.players]

		while any((lambda x: x[0])(info) for info in players_hand_info):
			
			dealer_action, target_p = self.dealer.decide(players_hand_info)
			self.dealer.action(dealer_action, self.players[target_p], self.deck)
			players_hand_info = [p.get_curr_hand_info() for p in self.players]

class Session:

	def __init__(self, no_games: int, game_ruleset: GameRuleset, players: list[Player], dealer: Dealer):
		self.no_games = no_games
		self.players = players
		self.dealer = dealer
		self.game_ruleset = game_ruleset

	def simulate(self):
		
		for i in range(self.no_games):
			game = Game(self.dealer, self.players, self.game_ruleset)
			game.play()

if __name__ == "__main__":
	
	bs = BettingStrategy()
	ps = PlayerStrategy()
	ds = DealerStrategy()
	rs = GameRuleset()
	players = [Player(50, bs, ps)]
	dealer = Dealer(50, ds)
	s = Session(5, rs, players, dealer)
	s.simulate()
from enum import Enum, auto
from typing import Tuple
from collections import deque
from itertools import product, starmap
from random import shuffle, randint
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
		self.cards: list[Card] = []
		self.state = self.State.CLOSED

	def draw_one(self, deck: Deck):
		self.cards.append(deck.draw())
	
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

class PlayerStrategy(ABC):

	def __init__(self, ruleset: GameRuleset):
		super().__init__()
		self.ruleset = ruleset
	
	@abstractmethod
	def determine_action(self, hand: Hand, history: list[Tuple[bool, Hand, int, int]]) -> 'Player.Action':
		pass

class DealerStrategy(ABC):
	
	def __init__(self, ruleset: GameRuleset):
		super().__init__()
		self.ruleset = ruleset

	@abstractmethod
	def determine_action(self, hand: Hand, history: list[Tuple[Hand, int, int, int]], player_info: Tuple[Hand.State, Hand | int]) -> Tuple['Dealer.Action.RESOLVE', int] | 'Dealer.Action.HIT':
		pass

class Player(GamePlayer):

	class Action(Enum):

		RUN = auto(),
		HIT = auto(),
		STAND = auto()

	def __init__(self, initial_bankroll: int, betting_strat: BettingStrategy, player_strat: PlayerStrategy):
		super().__init__()
		self.bankroll = initial_bankroll
		self.games_played = 0
		self.curr_bet = 0
		self.history = [] # (is_win: bool, hand: Hand, bet: int, new_bankroll: int)
		self.betting_strat = betting_strat
		self.player_strat = player_strat
	
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
			return

		if action is Player.Action.HIT:
			self.hand.draw_one(deck)
			if self.ruleset.hand_value(self.hand) > 21:
				self.bust = True

class Dealer(GamePlayer):

	class Action(Enum):

		HIT = auto(),
		RESOLVE = auto()

	def __init__(self, initial_bankroll: int, dealer_strat: DealerStrategy):
		super().__init__()
		self.bankroll = initial_bankroll
		self.games_played = 0
		self.dealer_strat = dealer_strat
		self.history = [] # (hand: Hand, no_win: int, no_lose: int, new_bankroll: int)

	def decide(self, player_info: Tuple[Hand.State, Hand | int]) -> Tuple['Dealer.Action.RESOLVE', int] | 'Dealer.Action.HIT':
		self.dealer_strat.determine_action(self.hand, self.history, player_info)

	def action(self, action: 'Dealer.Action', target_player: Player, deck: Deck):

		if action is Dealer.Action.HIT:
			self.hand.draw_one(deck)
			if self.ruleset.hand_value(self.hand) > 21:
				self.bust = True
		if action is Dealer.Action.RESOLVE:

			dealer_hand_value = self.ruleset.hand_value(self.hand)
			player_hand_value = self.ruleset.hand_value(target_player.hand)

			dealer_win = False

			if dealer_hand_value > player_hand_value or (target_player.bust is True and dealer.bust is False): # dealer win
				payout_mult = self.ruleset.payout_multiplier(target_player.hand)
				winnings = payout_mult * target_player.bet
				self.bankroll -= winnings
				target_player.bankroll += winnings
				dealer_win = True
				
			elif player_hand_value > dealer or (dealer.bust is True and target_player.bust is False): # player win
				payout_mult = self.ruleset.payout_multiplier(self.hand)
				winnings = payout_mult * target_player.bet
				self.bankroll += winnings
				target_player.bankroll -= winnings
				dealer_win = False
			else: # else push
				pass
			
			target_player.history.append((not dealer_win, target_player.hand, target_player.bet, target_player.bankroll))
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
			while player_action is not Player.Action.STAND:
				player_action = self.players[p].decide()
				self.players[p].action(player_action, self.deck)

	def _dealer_turn(self):

		players_hand_info = [p.get_curr_hand_info() for p in self.players]

		# dealers turn until all players have been resolved
		while any((lambda x: x[0] == Hand.State.CLOSED)(info) for info in players_hand_info):
			
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
			print(f"Game {i}")
			game = Game(self.dealer, self.players, self.game_ruleset)
			game.play()

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
		
		if self.ruleset.hand_value(hand) == 15:
			return Player.Action.RUN

		if self.ruleset.hand_value(hand) < 16:
			return Player.Action.HIT

		return Player.Action.STAND

class RegularDealerStrategy(DealerStrategy):

	def determine_action(self, hand: Hand, history: list[Tuple[Hand, int, int, int]], player_info: Tuple[Hand.State, Hand | int]) -> Tuple['Dealer.Action.RESOLVE', int] | 'Dealer.Action.HIT':
		
		if self.ruleset.hand_value(hand) < 16:
			return Dealer.Action.HIT

		for i in range(len(player_info)):
			if player_info[i][0] == Hand.State.CLOSED:
				return Dealer.Action.RESOLVE, i

class ChineseBlackjackRuleset(GameRuleset):
	
	def hand_value(self, hand: Hand):

		value = 0
		for card in hand.cards:

			if card.value.value in ['J', 'Q', 'K']:
				value += 10
			elif card.value.value == 'A':
				if len(hand) <= 2:
					value += 11
				elif len(hand) == 3:
					value += 10 if (value + 10) < 21 else 1
				elif len(hand) > 3:
					value += 1
			else:
				value += int(card.value.value)

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
			hand.cards[0].value >= 8:
			return 2

		return 1

if __name__ == "__main__":
	
	rand_bs = RandomBettingStrategy(1, 2)
	flat_bs = FlatBettingStrategy(1)
	chinese_ruleset = ChineseBlackjackRuleset()
	ps = RegularPlayerStrategy(chinese_ruleset)
	ds = RegularDealerStrategy(chinese_ruleset)
	
	players = [Player(20, rand_bs, ps) for _ in range(4)] + [Player(20, flat_bs, ps)]
	dealer = Dealer(20, ds)
	s = Session(50, chinese_ruleset, players, dealer)
	s.simulate()
import pygame
import sys
import random
from collections import Counter
import time
import copy

# mcts_ai.py 파일에서 MCTS_AI 클래스를 가져옵니다.
from mcts_ai import MCTS_AI

# --- 상수 정의 ---
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 750
FPS = 60
# 색상
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (100, 100, 100)
VALID_COLOR = (100, 255, 100)
INVALID_COLOR = (255, 100, 100)
# 카드 그래픽
CARD_WIDTH, CARD_HEIGHT, CARD_OVERLAP, CARD_BORDER_RADIUS = 60, 90, 25, 8
AI_CARD_WIDTH, AI_CARD_HEIGHT, AI_CARD_OVERLAP = 30, 45, 8
CARD_BACK_COLOR = (41, 128, 185)
CARD_RANK_COLORS = [
    (255, 255, 255), (230, 57, 70), (244, 162, 97), (233, 196, 106),
    (168, 218, 181), (69, 123, 157), (29, 53, 87), (162, 210, 255),
    (106, 76, 147), (255, 130, 130), (255, 190, 11), (247, 37, 133),
    (131, 56, 236), (80, 80, 80)
]

# ==============================================================================
# Player 클래스
# ==============================================================================
class Player:
    def __init__(self, name, is_ai=False, style='balanced'):
        self.name = name
        self.is_ai = is_ai
        self.style = style
        self.hand = []

    def sort_hand(self):
        self.hand.sort()

# ==============================================================================
# GameState 클래스 (핵심 로직)
# ==============================================================================
class GameState:
    def __init__(self, player_styles):
        self.num_players = len(player_styles)
        self.players = []
        is_human_in_game = "You" in player_styles
        for i, style in enumerate(player_styles):
            is_ai = is_human_in_game and i != player_styles.index("You") or not is_human_in_game
            name = "You" if not is_ai and is_human_in_game else f"AI {i+1}"
            self.players.append(Player(name, is_ai=is_ai, style=style))

        self.turn_index = 0
        self.round_lead_index = 0
        self.table_cards = {'cards': [], 'effective_rank': 0}
        self.passed_in_round = set()
        self.consecutive_passes = 0
        self.game_over = False
        self.winner_index = -1
        self.game_log = []
        self._setup_deck_and_deal()

    def _setup_deck_and_deal(self):
        deck = [c for i in range(1, 13) for c in [i] * i] + [13, 13]
        random.shuffle(deck)
        for i, card in enumerate(deck): self.players[i % self.num_players].hand.append(card)
        for p in self.players: p.sort_hand()
        self.turn_index = self.round_lead_index = random.randint(0, self.num_players - 1)
        self.game_log.append("--- New Game Started ---")

    def get_current_player(self):
        return self.players[self.turn_index]

    def get_possible_moves(self):
        if self.turn_index in self.passed_in_round:
            return ["pass"]
        
        moves = []
        player = self.get_current_player()
        hand_counts = Counter(player.hand)
        num_jokers = hand_counts.get(13, 0)
        
        for r_to_play in range(1, 14):
            max_count = hand_counts.get(r_to_play, 0) if r_to_play != 13 else num_jokers
            if r_to_play != 13: max_count += num_jokers
            
            for c_to_play in range(1, max_count + 1):
                if self.is_valid_move(self.turn_index, r_to_play, c_to_play):
                    moves.append({'rank': r_to_play, 'count': c_to_play})
        moves.append("pass")
        return moves

    def make_move(self, move):
        new_state = copy.deepcopy(self)
        if move == "pass":
            new_state.player_pass(new_state.turn_index)
        else:
            new_state.play_cards(new_state.turn_index, move['rank'], move['count'])
        return new_state

    def is_valid_move(self, player_index, rank, count):
        player = self.players[player_index]
        if player_index in self.passed_in_round: return False
        
        num_jokers = player.hand.count(13)
        if rank == 13:
            if num_jokers < count: return False
        else:
            num_native = player.hand.count(rank)
            if num_native + num_jokers < count: return False
        
        if not self.table_cards['cards']: return True
        if count == len(self.table_cards['cards']) and rank < self.table_cards['effective_rank']: return True
        return False

    def play_cards(self, player_index, rank, count):
        player = self.players[player_index]
        if rank == 13:
            to_remove = {'native': 0, 'jokers': count}
        else:
            native_available = player.hand.count(rank)
            jokers_to_use = count - native_available if native_available < count else 0
            native_to_use = count - jokers_to_use
            to_remove = {'native': native_to_use, 'jokers': jokers_to_use}
        
        for _ in range(to_remove['native']): player.hand.remove(rank)
        for _ in range(to_remove['jokers']): player.hand.remove(13)

        played_list = [rank] * to_remove['native'] + [13] * to_remove['jokers']
        played_list.sort()
        self.table_cards = {'cards': played_list, 'effective_rank': rank}
        self.game_log.append(f"{player.name} plays {count}x card {rank} (eff).")
        self.consecutive_passes = 0
        self.round_lead_index = player_index
        # self.passed_in_round.clear()

        if not player.hand:
            self.game_over = True
            self.winner_index = player_index
            self.game_log.append(f"🎉 {player.name} wins the game! 🎉")
            return
        self.advance_turn()

    def player_pass(self, player_index):
        """ 플레이어가 자발적으로 패스할 때 호출됩니다. """
        player = self.players[player_index]
        self.game_log.append(f"{player.name} passes.")
        self.passed_in_round.add(player_index)
        # 공통 로직 호출
        self._perform_pass_logic(player_index)

    def _perform_pass_logic(self, player_index):
        """ 자발적/자동 패스의 공통 로직을 처리합니다. (턴 넘김, 새 라운드 확인 등) """
        self.consecutive_passes += 1
        
        active_players = sum(1 for p in self.players if p.hand)
        if self.consecutive_passes >= active_players - 1 and active_players > 0:
            self.game_log.append(f"--- New round starts ---")
            self.table_cards = {'cards': [], 'effective_rank': 0}
            self.consecutive_passes = 0
            self.passed_in_round.clear()
            self.turn_index = self.round_lead_index
            # 새 라운드의 선 플레이어가 카드가 없으면 다음 사람에게 턴을 넘김
            if not self.players[self.turn_index].hand:
                self.advance_turn()
        else:
            self.advance_turn()
    
    def advance_turn(self):
        """ 순수하게 다음 플레이어로 턴 인덱스만 넘깁니다. """
        if self.game_over: return
        self.turn_index = (self.turn_index + 1) % self.num_players
        while not self.players[self.turn_index].hand:
            self.turn_index = (self.turn_index + 1) % self.num_players
            
# ==============================================================================
# Game 클래스 (Pygame 및 사용자 입력 담당)
# ==============================================================================
class Game:
    def __init__(self):
        pygame.init()
        # self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)

        pygame.display.set_caption("The Great Dalmuti")
        self.clock = pygame.time.Clock()
        try:
            self.font = pygame.font.SysFont("malgungothic", 24)
            self.small_font = pygame.font.SysFont("malgungothic", 18)
            self.card_font = pygame.font.SysFont("arial", 22, bold=True)
        except pygame.error:
            self.font = pygame.font.SysFont(None, 30)
            self.small_font = pygame.font.SysFont(None, 24)
            self.card_font = pygame.font.SysFont(None, 28, bold=True)

        self.game_state_manager = None
        self.game_mode = 'SETUP'
        self.selected_num_players = 4
        self.ai_styles = ['mcts', 'balanced', 'aggressive', 'defensive']
        self.ai_style_selections = [0] * 7
        # self.minus_button_rect = pygame.Rect(SCREEN_WIDTH/2 - 100, 150, 50, 50)
        # self.plus_button_rect = pygame.Rect(SCREEN_WIDTH/2 + 50, 150, 50, 50)
        # self.start_button_rect = pygame.Rect(SCREEN_WIDTH/2 - 100, SCREEN_HEIGHT - 100, 200, 50)
        # self.submit_button_rect = pygame.Rect(SCREEN_WIDTH/2 - 150, SCREEN_HEIGHT - 170, 140, 50)
        # self.pass_button_rect = pygame.Rect(SCREEN_WIDTH/2 + 10, SCREEN_HEIGHT - 170, 140, 50)
        self.minus_button_rect = None
        self.plus_button_rect = None
        self.start_button_rect = None
        self.submit_button_rect = None
        self.pass_button_rect = None

        self.selected_cards = []
        self.last_ai_move_time = 0
        self.time_delay = 2.0
        self.stealth_mode = True
        self.previous_turn_index = -1

    def run(self):
        while True:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

    def start_new_game(self, num_players, style_selections):
        player_styles = ["You"]
        for i in range(1, num_players):
            style_index = style_selections[i-1]
            player_styles.append(self.ai_styles[style_index])
        
        # GameState 객체를 생성합니다. 이 시점에 turn_index가 생성됩니다.
        self.game_state_manager = GameState(player_styles)
        self.game_mode = 'PLAYING'
        
        self.previous_turn_index = -1
        
        self.selected_cards = []
        self.last_ai_move_time = time.time()
        self.ai_thinking_log_added = False

    def handle_events(self, event_list=None):
        events = event_list if event_list is not None else pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if event.type == pygame.VIDEORESIZE:
                width, height = event.w, event.h
                # 최소 크기 제한
                if width < 800: width = 800
                if height < 600: height = 600
                self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.is_running = False
            
                # --- 스텔스 모드 토글 키 추가 ---
                if event.key == pygame.K_t:
                    self.stealth_mode = not self.stealth_mode

            if self.game_mode == 'SETUP': self.handle_setup_events(event)
            elif self.game_mode == 'PLAYING': self.handle_playing_events(event)
            elif self.game_mode == 'GAME_OVER':
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r: self.game_mode = 'SETUP'

    def handle_setup_events(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.minus_button_rect.collidepoint(event.pos) and self.selected_num_players > 2: self.selected_num_players -= 1
            elif self.plus_button_rect.collidepoint(event.pos) and self.selected_num_players < 8: self.selected_num_players += 1
            elif self.start_button_rect.collidepoint(event.pos): self.start_new_game(self.selected_num_players, self.ai_style_selections)
            # --- AI 스타일 변경 버튼 클릭 감지 (핵심 추가) ---
            width, height = self.screen.get_width(), self.screen.get_height()
            start_y = height * 0.5
            arrow_w, arrow_h = 30, 30
            for i in range(1, self.selected_num_players):
                current_y = start_y + (i - 1) * 50
                
                # 그리기 함수와 동일한 방식으로 버튼 위치를 실시간으로 계산
                left_arrow_rect = pygame.Rect(width/2 - 120, current_y - arrow_h/2, arrow_w, arrow_h)
                right_arrow_rect = pygame.Rect(width/2 + 90, current_y - arrow_h/2, arrow_w, arrow_h)

                if left_arrow_rect.collidepoint(event.pos):
                    current_style_index = self.ai_style_selections[i-1]
                    self.ai_style_selections[i-1] = (current_style_index - 1) % len(self.ai_styles)
                elif right_arrow_rect.collidepoint(event.pos):
                    current_style_index = self.ai_style_selections[i-1]
                    self.ai_style_selections[i-1] = (current_style_index + 1) % len(self.ai_styles)
    
    def handle_playing_events(self, event):
        """ 게임 진행 중 마우스 클릭 이벤트를 처리합니다. """
        state = self.game_state_manager
        human_player_index = 0
        is_my_turn = (state.turn_index == human_player_index and not state.players[human_player_index].is_ai)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and is_my_turn:
            
            # [Submit] 버튼 클릭
            if self.submit_button_rect.collidepoint(event.pos):
                if self.selected_cards:
                    hand = state.players[human_player_index].hand
                    
                    # --- 핵심 버그 수정: 제출 등급(rank)을 명확하게 결정 ---
                    selected_ranks = [hand[i] for i in self.selected_cards]
                    non_joker_ranks = [r for r in selected_ranks if r != 13]

                    if not non_joker_ranks:
                        # Case 1: 조커만 선택된 경우. 등급은 무조건 13.
                        rank_to_play = 13
                    else:
                        # Case 2: 다른 숫자와 조커가 섞인 경우. 등급은 다른 숫자의 등급.
                        # (handle_card_click 로직이 다른 종류의 숫자카드는 함께 선택 못하게 막아줌)
                        rank_to_play = non_joker_ranks[0]
                    # --- 수정 종료 ---
                    
                    count_to_play = len(self.selected_cards)

                    if state.is_valid_move(human_player_index, rank_to_play, count_to_play):
                        state.play_cards(human_player_index, rank_to_play, count_to_play)
                        self.selected_cards.clear()
                    else:
                        state.game_log.append("You can't play that.")
                else:
                    state.game_log.append("No cards selected.")
            
            # [Pass] 버튼 클릭
            elif self.pass_button_rect.collidepoint(event.pos):
                state.player_pass(human_player_index)
                self.selected_cards.clear()
            
            # 카드 영역 클릭
            else:
                self.handle_card_click(event.pos)

    def handle_card_click(self, mouse_pos):
        """ 카드 클릭을 처리하여 카드를 선택하거나 해제합니다. (조커 포함) """
        state = self.game_state_manager
        human_player = state.players[0]
        hand = human_player.hand
        
        if not hand: return

        # 그리기 로직과 동일하게 카드 위치를 계산해야 정확한 클릭 감지가 가능
        hand_base_y = SCREEN_HEIGHT - CARD_HEIGHT - 20
        total_hand_width = CARD_WIDTH + (len(hand) - 1) * CARD_OVERLAP
        start_x = (SCREEN_WIDTH - total_hand_width) / 2

        clicked_card_index = -1

        # 맨 위 카드(가장 오른쪽)부터 순회하여 어떤 카드를 클릭했는지 확인
        for i in range(len(hand) - 1, -1, -1):
            card_y = hand_base_y - 20 if i in self.selected_cards else hand_base_y
            
            # 각 카드의 정확한 사각형 위치 계산
            card_rect = pygame.Rect(start_x + i * CARD_OVERLAP, card_y, CARD_WIDTH, CARD_HEIGHT)
            
            # 겹쳐진 카드이므로, 마지막 카드가 아니면 보이는 부분(겹치는 너비)만 클릭 영역으로 인정
            if i < len(hand) - 1:
                card_rect.width = CARD_OVERLAP

            if card_rect.collidepoint(mouse_pos):
                clicked_card_index = i
                break # 맨 위 카드를 찾았으므로 더 이상 검사할 필요 없음
        
        # 카드를 정확히 클릭했다면, 선택 로직 실행
        if clicked_card_index != -1:
            clicked_rank = hand[clicked_card_index]
            
            # 이미 선택된 카드를 다시 클릭한 경우: 선택 해제
            if clicked_card_index in self.selected_cards:
                self.selected_cards.remove(clicked_card_index)
            
            # 새로운 카드를 클릭한 경우: 선택 추가
            else:
                # 선택된 카드가 하나도 없다면, 무조건 추가
                if not self.selected_cards:
                    self.selected_cards.append(clicked_card_index)
                else:
                    # 현재 선택된 카드의 기준 등급(rank) 찾기 (조커가 아닐 경우)
                    selected_rank = -1
                    for idx in self.selected_cards:
                        if hand[idx] != 13:
                            selected_rank = hand[idx]
                            break
                    
                    # 조커만 선택되어 있었다면, 새로 클릭한 카드가 기준이 됨
                    if selected_rank == -1:
                        selected_rank = clicked_rank

                    # 새로 클릭한 카드가 조커이거나, 기준 등급과 같다면 선택 목록에 추가
                    if clicked_rank == selected_rank or clicked_rank == 13:
                        self.selected_cards.append(clicked_card_index)
                    # 다른 등급의 카드를 클릭했다면, 기존 선택을 모두 초기화하고 새로 선택
                    else:
                        self.selected_cards.clear()
                        self.selected_cards.append(clicked_card_index)
    
    def update(self):
        """ 게임 상태를 업데이트하고 AI 턴을 관리합니다. """
        mouse_pos = pygame.mouse.get_pos()
        cursor_on_button = False

        # GameState가 아직 생성되지 않았다면 아무것도 하지 않음
        if not self.game_state_manager:
            if self.game_mode == 'SETUP':
                # ... (이 부분은 기존 설정 화면 커서 로직과 동일하게 유지됩니다) ...
                pass
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if cursor_on_button else pygame.SYSTEM_CURSOR_ARROW)
            return

        # 이제부터 모든 게임 상태는 'state' 변수를 통해 접근합니다.
        state = self.game_state_manager

        if self.game_mode == 'PLAYING':
            # 게임 오버 상태로 전환
            if state.game_over:
                self.game_mode = 'GAME_OVER'
                return

            # 턴 변경 감지 및 AI 타이머 설정
            if state.turn_index != self.previous_turn_index:
                if state.players[state.turn_index].is_ai:
                    self.last_ai_move_time = time.time()
                
                # 턴이 바뀌었으므로, 이전 '생각 중' 로그 상태를 리셋합니다.
                self.ai_thinking_log_added = False
                self.previous_turn_index = state.turn_index
                

            current_player = state.players[state.turn_index]
            
            # 자동 패스 로직
            if state.turn_index in state.passed_in_round:
                if time.time() - self.last_ai_move_time > self.time_delay / 2:
                    # 자동 패스 로직은 player_pass 함수 내에서 처리되므로 여기선 호출만 합니다.
                    state.player_pass(state.turn_index)
                    self.last_ai_move_time = time.time() # 타이머 리셋
            # AI 턴 진행
            elif current_player.is_ai:
                # 이번 턴에 아직 '생각 중' 로그를 추가하지 않았다면, 추가합니다.
                if not self.ai_thinking_log_added:
                    state.game_log.append(f"{current_player.name} is thinking...")
                    self.ai_thinking_log_added = True
                    self.last_ai_move_time = time.time() # 타이머는 로그 추가 시점에 시작
                
                if time.time() - self.last_ai_move_time > self.time_delay:
                    self.run_ai_turn()
            
            # 커서 로직
            can_play = (state.turn_index == 0 and not state.players[0].is_ai and 0 not in state.passed_in_round)
            if can_play and (self.submit_button_rect.collidepoint(mouse_pos) or self.pass_button_rect.collidepoint(mouse_pos)):
                cursor_on_button = True

        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if cursor_on_button else pygame.SYSTEM_CURSOR_ARROW)
    def run_ai_turn(self):
        """ AI의 턴을 실행하고, 스타일에 맞는 로직을 호출합니다. """
        state = self.game_state_manager
        player = state.get_current_player()
        style = player.style

        # --- 핵심 수정: AI가 행동하기 직전에 "생각 중..." 로그를 제거 ---
        if self.ai_thinking_log_added:
            state.game_log.pop()
            self.ai_thinking_log_added = False

        # ======================================================
        # MCTS AI 로직
        # ======================================================
        if style == 'mcts':
            print(f"{player.name} (MCTS) is thinking...")
            # MCTS AI 객체를 생성하고, 현재 게임 상태를 넘겨 최선의 수를 찾게 함
            # iterations를 높이면 더 똑똑해지지만, 생각하는 시간이 길어집니다.
            mcts_player = MCTS_AI(iterations=1000) 
            best_move = mcts_player.find_best_move(initial_state=state)
            
            # MCTS가 결정한 수를 실행
            if best_move == "pass":
                state.player_pass(state.turn_index)
            else:
                state.play_cards(state.turn_index, best_move['rank'], best_move['count'])

        # ======================================================
        # 규칙 기반 AI 로직 (Aggressive, Defensive, Balanced)
        # ======================================================
        else:
            # --- 1. 가능한 모든 수를 찾는다 ---
            possible_plays = []
            hand_counts = Counter(player.hand)
            num_jokers = hand_counts.get(13, 0)
            is_start_of_round = not state.table_cards['cards']

            # 1-1. 조커 없이 낼 수 있는 경우
            for r, c in hand_counts.items():
                if r == 13: continue
                if state.is_valid_move(state.turn_index, r, c):
                    possible_plays.append({'rank': r, 'count': c, 'jokers_used': 0, 'is_start': is_start_of_round})
            
            # 1-2. 조커를 섞어 낼 수 있는 경우
            if num_jokers > 0:
                for r, c in hand_counts.items():
                    if r == 13: continue
                    for j in range(1, num_jokers + 1):
                        if state.is_valid_move(state.turn_index, r, c + j):
                            possible_plays.append({'rank': r, 'count': c + j, 'jokers_used': j, 'is_start': is_start_of_round})
            
            # 1-3. 조커만 내는 경우
            if num_jokers > 0:
                if state.is_valid_move(state.turn_index, 13, num_jokers):
                    possible_plays.append({'rank': 13, 'count': num_jokers, 'jokers_used': num_jokers, 'is_start': is_start_of_round})
                if num_jokers > 1 and state.is_valid_move(state.turn_index, 13, 1):
                     possible_plays.append({'rank': 13, 'count': 1, 'jokers_used': 1, 'is_start': is_start_of_round})

            # --- 2. 낼 패가 없으면 패스 ---
            if not possible_plays:
                state.player_pass(state.turn_index)
                self.last_ai_move_time = time.time()
                return

            # --- 3. 스타일에 따라 최선의 수를 결정한다 ---
            best_play = None
            
            if style == 'aggressive':
                # 공격형: 1.조커사용 최소화, 2.라운드시작시 카드수 최대화, 3.가치낮은(숫자 큰)카드부터
                possible_plays.sort(key=lambda p: (p['jokers_used'], -p['count'] if p['is_start'] else 0, p['rank']))
                best_play = possible_plays[0]

            elif style == 'defensive':
                # 수비형: 1.조커사용 극도로 회피, 2.가치낮은(숫자 큰)카드부터, 3.카드수 최대화
                possible_plays.sort(key=lambda p: (p['jokers_used'] * 10, p['rank'], -p['count']))
                best_play = possible_plays[0]
            
            else: # 'balanced' (중간형)
                # 중간형: 1.조커사용 최소화, 2.가치낮은(숫자 큰)카드부터
                possible_plays.sort(key=lambda p: (p['jokers_used'], p['rank']))
                best_play = possible_plays[0]
            
            state.play_cards(state.turn_index, best_play['rank'], best_play['count'])

        # AI의 행동이 끝난 시간을 기록
        self.last_ai_move_time = time.time()

    def draw(self):
        self.screen.fill(BLACK)
        if self.game_mode == 'SETUP': self.draw_setup_screen()
        elif self.game_mode in ['PLAYING', 'GAME_OVER']:
            if self.game_state_manager: self.draw_game_screen()
        pygame.display.flip()

    def draw_setup_screen(self):
        """ 플레이어 수와 AI 스타일 설정 화면을 그립니다. (창 크기 반응형) """
        width, height = self.screen.get_width(), self.screen.get_height()

        # --- 플레이어 수 설정 UI ---
        self.draw_text("Select Number of Players", self.font, WHITE, width / 2, height * 0.2)
        
        button_w, button_h = 50, 50
        self.minus_button_rect = pygame.Rect(width/2 - 100, height * 0.3 - button_h/2, button_w, button_h)
        self.plus_button_rect = pygame.Rect(width/2 + 50, height * 0.3 - button_h/2, button_w, button_h)

        minus_color = GRAY if self.selected_num_players <= 2 else WHITE
        plus_color = GRAY if self.selected_num_players >= 8 else WHITE
        
        pygame.draw.rect(self.screen, minus_color, self.minus_button_rect, 2)
        self.draw_text("-", self.font, minus_color, self.minus_button_rect.centerx, self.minus_button_rect.centery)
        self.draw_text(str(self.selected_num_players), self.font, WHITE, width / 2, height * 0.3)
        pygame.draw.rect(self.screen, plus_color, self.plus_button_rect, 2)
        self.draw_text("+", self.font, plus_color, self.plus_button_rect.centerx, self.plus_button_rect.centery)

        # --- AI 스타일 설정 UI ---
        self.draw_text("Set AI Player Styles", self.font, WHITE, width / 2, height * 0.45)
        
        start_y = height * 0.5
        for i in range(1, self.selected_num_players):
            current_y = start_y + (i - 1) * 50
            self.draw_text_left(f"AI {i}:", self.font, WHITE, width/2 - 240, current_y - 15)
            
            # '<' 버튼
            left_arrow_rect = pygame.Rect(width/2 - 120, current_y - 15, button_w/1.5, button_h/1.5)
            pygame.draw.rect(self.screen, WHITE, left_arrow_rect, 2)
            self.draw_text("<", self.font, WHITE, left_arrow_rect.centerx, left_arrow_rect.centery)
            
            # 현재 스타일
            style_index = self.ai_style_selections[i-1]
            style_name = self.ai_styles[style_index].capitalize()
            self.draw_text(style_name, self.font, WHITE, width/2, current_y)

            # '>' 버튼
            right_arrow_rect = pygame.Rect(width/2 + 90, current_y - 15, button_w/1.5, button_h/1.5)
            pygame.draw.rect(self.screen, WHITE, right_arrow_rect, 2)
            self.draw_text(">", self.font, WHITE, right_arrow_rect.centerx, right_arrow_rect.centery)

        # --- 시작 버튼 ---
        self.start_button_rect = pygame.Rect(width/2 - 100, height - 100, 200, 50)
        pygame.draw.rect(self.screen, VALID_COLOR, self.start_button_rect)
        self.draw_text("Start Game", self.font, BLACK, self.start_button_rect.centerx, self.start_button_rect.centery)

    def draw_game_screen(self):
        """ 게임 진행 중 화면을 그립니다. (창 크기 반응형) """
        width, height = self.screen.get_width(), self.screen.get_height()
        state = self.game_state_manager
        
        # 상단 제목
        self.draw_text("The Great Dalmuti", self.font, WHITE, width / 2, 30)

        # 게임 오버 화면
        if self.game_mode == 'GAME_OVER' and state.winner_index != -1:
            winner_name = state.players[state.winner_index].name
            self.draw_text(f"{winner_name} is the Winner!", self.font, VALID_COLOR, width / 2, height / 2 - 40)
            self.draw_text("Press 'R' to Restart", self.font, WHITE, width / 2, height / 2 + 20)
            return
        # --- 카드 크기 동적 조절 ---
        card_w = max(40, int(width * 0.06))
        card_h = int(card_w * 1.5)
        card_overlap = int(card_w * 0.4)
        ai_card_w = max(20, int(width * 0.03))
        ai_card_h = int(ai_card_w * 1.5)
        ai_card_overlap = int(ai_card_w * 0.25)

        # --- AI 플레이어 패널 (화면 우측) ---
        ai_area_x = width - 220
        ai_area_y = 80

        self.draw_text_left("--- Other Players ---", self.small_font, WHITE, ai_area_x, ai_area_y)
        ai_area_y += 25

        for i, player in enumerate(state.players):
            if i == 0: continue # 자신은 제외
            
            hand_count = len(player.hand)
            player_info_text = f"{player.name} ({player.style[:4].capitalize()}) ({hand_count})"
            self.draw_text_left(player_info_text, self.small_font, WHITE, ai_area_x, ai_area_y)

            # 상태 표시 (선, 턴, 패스)
            status_indicators = []
            if i == state.round_lead_index: status_indicators.append(('✔', WHITE))
            if i == state.turn_index: status_indicators.append(('Turn', VALID_COLOR))
            elif i in state.passed_in_round: status_indicators.append(('Pass', INVALID_COLOR))
            
            current_x_offset = self.small_font.size(player_info_text)[0] + 10
            for text, color in status_indicators:
                self.draw_text_left(text, self.small_font, color, ai_area_x + current_x_offset, ai_area_y)
                current_x_offset += self.small_font.size(text)[0] + 10

            ai_area_y += 20
            if hand_count > 0:
                for card_idx in range(hand_count):
                    card_x = ai_area_x + card_idx * AI_CARD_OVERLAP
                    card_rect = pygame.Rect(card_x, ai_area_y, AI_CARD_WIDTH, AI_CARD_HEIGHT)

                    if self.stealth_mode:
                        back_color, border_color = WHITE, BLACK
                    else:
                        back_color, border_color = CARD_BACK_COLOR, BLACK
                    
                    pygame.draw.rect(self.screen, back_color, card_rect, border_radius=4)
                    pygame.draw.rect(self.screen, border_color, card_rect, 1, border_radius=4)

            ai_area_y += AI_CARD_HEIGHT + 15
        
        # --- 테이블 위 카드 그리기 ---
        # --- 테이블 위 카드 (화면 중앙) ---
        if state.table_cards['cards']:
            cards_on_table = state.table_cards['cards']
            count = len(cards_on_table)
            total_card_width = card_w + (count - 1) * card_overlap
            start_x = (width - total_card_width) / 2
            card_y = height / 2 - card_h / 2 - 30
            for i, rank_on_table in enumerate(cards_on_table):
                card_rect = pygame.Rect(start_x + i * CARD_OVERLAP, card_y, CARD_WIDTH, CARD_HEIGHT)
                #card_color = CARD_RANK_COLORS[rank_on_table]
                if self.stealth_mode:
                    card_color, border_color, text_color = WHITE, BLACK, BLACK
                else:
                    card_color, border_color, text_color = CARD_RANK_COLORS[rank_on_table], WHITE, WHITE
                
                pygame.draw.rect(self.screen, card_color, card_rect, border_radius=CARD_BORDER_RADIUS)
                pygame.draw.rect(self.screen, border_color, card_rect, 2, border_radius=CARD_BORDER_RADIUS)
                rank_str = "J" if rank_on_table == 13 else str(rank_on_table)
                rank_text = self.card_font.render(rank_str, True, text_color)
                self.screen.blit(rank_text, (card_rect.x + 7, card_rect.y + 5))
            
        # --- 플레이어 카드 그리기 ---
        human_player = state.players[0]
        hand = human_player.hand
        hand_base_y = height - card_h - 20
        if hand:
            total_card_width = card_w + (len(hand) - 1) * card_overlap
            start_x = (width - total_card_width) / 2
            for i, rank in enumerate(hand):
                card_y = hand_base_y - 20 if i in self.selected_cards else hand_base_y
                card_rect = pygame.Rect(start_x + i * card_overlap, card_y, card_w, card_h)

                if self.stealth_mode:
                    card_color, border_color, text_color = WHITE, BLACK, BLACK
                else:
                    card_color, border_color, text_color = CARD_RANK_COLORS[rank], WHITE, WHITE

                pygame.draw.rect(self.screen, card_color, card_rect, border_radius=CARD_BORDER_RADIUS)
                pygame.draw.rect(self.screen, border_color, card_rect, 2, border_radius=CARD_BORDER_RADIUS)
                rank_str = "J" if rank == 13 else str(rank)
                rank_text = self.card_font.render(rank_str, True, text_color)
                self.screen.blit(rank_text, (card_rect.x + 7, card_rect.y + 5))
        
        # --- 하단 UI 요소 그리기 ---
        turn_info = f"Current Turn: {state.get_current_player().name}"
        if state.round_lead_index == 0:
            turn_info += " (You are the Leader ✔)"
        self.draw_text(turn_info, self.font, WHITE, width / 2, 80)
        
        can_play = (state.turn_index == 0 and not state.players[0].is_ai and 0 not in state.passed_in_round)
        if self.stealth_mode:
            submit_bg_color = WHITE if can_play else GRAY
            pass_bg_color = WHITE if can_play else GRAY
        else:
            submit_bg_color = VALID_COLOR if can_play else GRAY
            pass_bg_color = INVALID_COLOR if can_play else GRAY

        submit_text_color = BLACK if can_play else (50, 50, 50)
        pass_text_color = BLACK if can_play else (50, 50, 50)
        
        self.submit_button_rect = pygame.Rect(width/2 - 150, height - 170, 140, 50)
        self.pass_button_rect = pygame.Rect(width/2 + 10, height - 170, 140, 50)

        pygame.draw.rect(self.screen, submit_bg_color, self.submit_button_rect)
        self.draw_text("Submit", self.font, submit_text_color, self.submit_button_rect.centerx, self.submit_button_rect.centery)
        pygame.draw.rect(self.screen, pass_bg_color, self.pass_button_rect)
        self.draw_text("Pass", self.font, pass_text_color, self.pass_button_rect.centerx, self.pass_button_rect.centery)

        # --- 게임 로그 그리기 (화면 좌측) ---
        log_y_pos = 80
        self.draw_text_left("--- Game Log ---", self.small_font, WHITE, 20, log_y_pos)
        log_y_pos += 25
        for log_line in state.game_log[-20:]:
            self.draw_text_left(log_line, self.small_font, GRAY, 20, log_y_pos)
            log_y_pos += 22

    def draw_text(self, text, font, color, x, y):
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect(center=(x, y))
        self.screen.blit(text_surface, text_rect)

    def draw_text_left(self, text, font, color, x, y):
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect(topleft=(x, y))
        self.screen.blit(text_surface, text_rect)

if __name__ == '__main__':
    game = Game()
    game.run()
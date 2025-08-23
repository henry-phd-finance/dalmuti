from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import ListProperty, NumericProperty, BooleanProperty, ObjectProperty
from kivy.core.window import Window
from kivy.clock import Clock
from functools import partial

# 우리가 만든 게임의 핵심 로직과 AI들을 가져옵니다.
from dalmuti_game import GameState
from mcts_ai import MCTS_AI
from collections import Counter

Window.clearcolor = (0.1, 0.1, 0.1, 1)

# --- 카드 등급별 색상 팔레트 (Kivy 0-1 스케일) ---
CARD_RANK_COLORS = [
    (1, 1, 1), # 0 - 사용 안 함
    (230/255.0, 57/255.0, 70/255.0),   # 1: Red
    (244/255.0, 162/255.0, 97/255.0),  # 2: Orange
    (233/255.0, 196/255.0, 106/255.0), # 3: Yellow
    (168/255.0, 218/255.0, 181/255.0), # 4: Mint
    (69/255.0, 123/255.0, 157/255.0),  # 5: Teal
    (29/255.0, 53/255.0, 87/255.0),    # 6: Navy
    (162/255.0, 210/255.0, 255/255.0), # 7: Sky Blue
    (106/255.0, 76/255.0, 147/255.0),  # 8: Purple
    (255/255.0, 130/255.0, 130/255.0), # 9: Pink
    (255/255.0, 190/255.0, 11/255.0),  # 10: Gold
    (247/255.0, 37/255.0, 133/255.0),  # 11: Magenta
    (131/255.0, 56/255.0, 236/255.0),  # 12: Light Purple
    (80/255.0, 80/255.0, 80/255.0)     # 13: Joker (Dark Gray)
]

# ==============================================================================
# 커스텀 위젯 정의
# ==============================================================================
class CardWidget(Button):
    rank = NumericProperty(0)

    def __init__(self, rank, **kwargs):
        super().__init__(**kwargs)
        self.rank = rank
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.background_down = ''
        
        self.text = "J" if rank == 13 else str(rank)
        self.font_size = '10sp'
        self.bold = False
        self.color = (1, 1, 1, 1)
        self.halign = 'left'
        self.valign = 'top'
        self.padding = (10, 10)
        
        with self.canvas.before:
            Color(rgb=CARD_RANK_COLORS[self.rank])
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[8])
            
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
        # Kivy 버튼의 text_size를 위젯 크기와 동일하게 설정하여 정렬 기준을 명확하게 함
        self.text_size = self.size

class PlayerHandWidget(RelativeLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.card_widgets = []

    def update_hand(self, hand_ranks, selected_indices):
        if self.width == 100 and self.height == 100:
            Clock.schedule_once(lambda dt: self.update_hand(hand_ranks, selected_indices))
            return

        self.clear_widgets()
        self.card_widgets = []
        total_cards = len(hand_ranks)
        if total_cards == 0: return

        ROW_THRESHOLD = 15

        def create_card_widget(rank, index, x, y, width, height):
            is_selected = index in selected_indices
            y_offset = 20 if is_selected else 0
            
            card = CardWidget(rank=rank, size=(width, height), pos=(x, y + y_offset), size_hint=(None, None))
            card.bind(on_press=partial(App.get_running_app().on_card_press, index))
            self.card_widgets.append(card)
            return card

        if total_cards <= ROW_THRESHOLD:
            card_width = self.width * 0.12
            card_height = self.height * 0.8
            render_area = self.width * 0.95
            
            step_x = (render_area - card_width) / (total_cards - 1) if total_cards > 1 else 0
            start_x = (self.width - (card_width + step_x * (total_cards - 1))) / 2
            
            for i, rank in enumerate(hand_ranks):
                self.add_widget(create_card_widget(rank, i, start_x + i * step_x, self.height * 0.1, card_width, card_height))
        else:
            top_row_count = total_cards // 2
            bottom_row_count = total_cards - top_row_count
            
            def process_row(count, ranks, start_idx, y_pos):
                card_width = self.width * 0.12
                card_height = self.height * 0.55
                render_area = self.width # 두 줄일 땐 공간을 100% 사용
                
                step_x = (render_area - card_width) / (count - 1) if count > 1 else 0
                start_x = (self.width - (card_width + step_x * (count - 1))) / 2
                
                for i in range(count):
                    self.add_widget(create_card_widget(ranks[i], start_idx + i, start_x + i * step_x, y_pos, card_width, card_height))

            process_row(top_row_count, hand_ranks[:top_row_count], 0, self.height * 0.4)
            process_row(bottom_row_count, hand_ranks[top_row_count:], top_row_count, self.height * 0.05)




class TableWidget(RelativeLayout):
    def update_table(self, cards_on_table):
        self.clear_widgets()
        count = len(cards_on_table)
        if count == 0: return

        card_width = self.width * 0.15
        card_height = self.height * 0.5
        total_render_width = self.width * 0.8
        overlap_px = (card_width * count - total_render_width) / (count - 1) if count > 1 else 0
        step_x = card_width - overlap_px if overlap_px > 0 else card_width
        start_x = (self.width - (card_width + step_x * (count - 1))) / 2
        
        for i, rank in enumerate(cards_on_table):
            self.add_widget(CardWidget(rank=rank, size=(card_width, card_height), pos=(start_x + i * step_x, self.height * 0.25), size_hint=(None, None)))

class OtherPlayersWidget(GridLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 1
        self.spacing = '10dp'
        self.size_hint_x = None
        self.width = '220dp'

    def update_players(self, players, turn_idx, lead_idx, passed_set):
        self.clear_widgets()
        self.add_widget(Label(text="--- Other Players ---", size_hint_y=None, height='30dp'))
        for i, player in enumerate(players):
            if i == 0: continue
            
            info_text = f"{player.name} ({player.style[:4].capitalize()}) ({len(player.hand)})"
            player_label = Label(text=info_text, size_hint_y=None, height='30dp')

            status_text = ""
            if i == lead_idx: status_text += " ✔"
            if i == turn_idx: player_label.color = (0.5, 1, 0.5, 1)
            elif i in passed_set: status_text += " (Pass)"; player_label.color = (1, 0.5, 0.5, 1)
            player_label.text += status_text
                
            self.add_widget(player_label)

class LogWidget(ScrollView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.log_label = Label(size_hint_y=None, markup=True, padding=(10, 10), halign='left', valign='top')
        self.log_label.bind(texture_size=self.log_label.setter('size'))
        self.add_widget(self.log_label)

    def update_log(self, log_list):
        self.log_label.text = "\n".join(log_list[-20:])
        self.scroll_y = 1

# ==============================================================================
# 메인 앱 클래스
# ==============================================================================
class DalmutiApp(App):
    selected_card_indices = ListProperty([])
    selected_num_players = NumericProperty(5)
    ai_style_selections = ListProperty([0] * 7)
    
    def build(self):
        self.title = "The Great Dalmuti"
        self.main_container = BoxLayout()
        self.go_to_setup_screen()
        return self.main_container

    def go_to_setup_screen(self, *args):
        self.main_container.clear_widgets()
        self.update_setup_screen()
        
    def update_setup_screen(self, *args):
        # build a new setup screen each time to reflect changes
        setup_layout = BoxLayout(orientation='vertical', spacing=10, padding=20)
        setup_layout.add_widget(Label(text="Game Setup", font_size='40sp', size_hint_y=0.2))

        player_count_layout = BoxLayout(size_hint_y=0.15, padding=(100, 0))
        minus_button = Button(text='-', font_size='30sp'); minus_button.bind(on_press=self.decrement_players)
        player_count_label = Label(text=str(self.selected_num_players), font_size='30sp')
        plus_button = Button(text='+', font_size='30sp'); plus_button.bind(on_press=self.increment_players)
        player_count_layout.add_widget(minus_button)
        player_count_layout.add_widget(player_count_label)
        player_count_layout.add_widget(plus_button)
        setup_layout.add_widget(player_count_layout)
        
        ai_styles_layout = GridLayout(cols=1, spacing=10, size_hint_y=0.5)
        self.ai_styles = ['balanced', 'aggressive', 'defensive', 'mcts']
        for i in range(1, self.selected_num_players):
            style_layout = BoxLayout(padding=(50,0))
            style_layout.add_widget(Label(text=f"AI {i}:"))
            left_button = Button(text='<'); left_button.bind(on_press=partial(self.change_ai_style, i - 1, -1))
            style_label = Label(text=self.ai_styles[self.ai_style_selections[i-1]].capitalize())
            right_button = Button(text='>'); right_button.bind(on_press=partial(self.change_ai_style, i - 1, 1))
            style_layout.add_widget(left_button)
            style_layout.add_widget(style_label)
            style_layout.add_widget(right_button)
            ai_styles_layout.add_widget(style_layout)
        setup_layout.add_widget(ai_styles_layout)

        start_button = Button(text='Start Game', font_size='24sp', size_hint_y=0.15)
        start_button.bind(on_press=self.start_game)
        setup_layout.add_widget(start_button)
        
        self.main_container.clear_widgets()
        self.main_container.add_widget(setup_layout)
        
    def decrement_players(self, instance):
        if self.selected_num_players > 2:
            self.selected_num_players -= 1
            self.update_setup_screen()
            
    def increment_players(self, instance):
        if self.selected_num_players < 8:
            self.selected_num_players += 1
            self.update_setup_screen()

    def change_ai_style(self, ai_index, direction, instance):
        current_index = self.ai_style_selections[ai_index]
        new_index = (current_index + direction) % len(self.ai_styles)
        self.ai_style_selections[ai_index] = new_index
        self.update_setup_screen()

    def start_game(self, instance):
        player_styles = ["You"] + [self.ai_styles[self.ai_style_selections[i]] for i in range(self.selected_num_players - 1)]
        self.game_state = GameState(player_styles)
        
        main_layout = self.create_main_game_layout()
        self.main_container.clear_widgets()
        self.main_container.add_widget(main_layout)
        Clock.schedule_once(lambda dt: self.update_ui())

        def create_main_game_layout(self):
        root = BoxLayout(spacing=10, padding=10)
        
        # --- 핵심 수정: 중앙 패널의 너비 비율(size_hint_x) 조정 ---
        self.log_widget = LogWidget(size_hint_x=0.25)
        center_layout = BoxLayout(orientation='vertical', size_hint_x=0.5, spacing=10)
        self.other_players_widget = OtherPlayersWidget(size_hint_x=0.25)
        # --- 수정 종료 ---

        self.table_widget = TableWidget(size_hint_y=0.4)
        self.player_hand_widget = PlayerHandWidget(size_hint_y=0.3, size_hint_x=0.15)
        action_bar = BoxLayout(size_hint_y=None, height='50dp', spacing=10)
        submit_button = Button(text='Submit'); submit_button.bind(on_press=self.on_submit)
        pass_button = Button(text='Pass'); pass_button.bind(on_press=self.on_pass)
        action_bar.add_widget(submit_button); action_bar.add_widget(pass_button)
        
        center_layout.add_widget(Label(text="Table", size_hint_y=None, height='30dp'))
        center_layout.add_widget(self.table_widget)
        center_layout.add_widget(Label(text="Your Hand", size_hint_y=None, height='30dp'))
        center_layout.add_widget(self.player_hand_widget)
        center_layout.add_widget(action_bar)

        root.add_widget(self.log_widget)
        root.add_widget(center_layout)
        root.add_widget(self.other_players_widget)
        return root


    def on_card_press(self, card_hand_index, *args):
        if self.game_state.turn_index != 0: return
        hand = self.game_state.players[0].hand
        
        if card_hand_index in self.selected_card_indices:
            self.selected_card_indices.remove(card_hand_index)
        else:
            clicked_rank = hand[card_hand_index]
            if self.selected_card_indices:
                base_rank = -1
                for idx in self.selected_card_indices:
                    if hand[idx] != 13:
                        base_rank = hand[idx]; break
                if base_rank == -1: base_rank = clicked_rank
                if clicked_rank != base_rank and clicked_rank != 13:
                    self.selected_card_indices.clear()
            self.selected_card_indices.append(card_hand_index)
        self.player_hand_widget.update_hand(hand, self.selected_card_indices)

    def on_submit(self, instance):
        if self.game_state.turn_index != 0 or not self.selected_card_indices: return
        hand = self.game_state.players[0].hand
        selected_ranks = [hand[i] for i in self.selected_card_indices]
        non_joker_ranks = [r for r in selected_ranks if r != 13]
        rank_to_play = 13 if not non_joker_ranks else non_joker_ranks[0]
        count_to_play = len(self.selected_card_indices)
        if self.game_state.is_valid_move(0, rank_to_play, count_to_play):
            self.game_state.play_cards(0, rank_to_play, count_to_play)
            self.selected_card_indices = []
            self.update_ui()
    
    def on_pass(self, instance):
        if self.game_state.turn_index != 0: return
        self.game_state.player_pass(0)
        self.selected_card_indices = []
        self.update_ui()

    def run_ai_turn(self, dt):
        state = self.game_state
        if state.game_over: return
        player = state.get_current_player()
        
        style = player.style
        if style == 'mcts':
            print(f"{player.name} (MCTS) is thinking...")
            mcts_player = MCTS_AI(iterations=1000)
            best_move = mcts_player.find_best_move(initial_state=state)
            if best_move == "pass": state.player_pass(state.turn_index)
            else: state.play_cards(state.turn_index, best_move['rank'], best_move['count'])
        else:
            possible_plays = []
            hand_counts = Counter(player.hand)
            num_jokers = hand_counts.get(13, 0)
            is_start = not state.table_cards['cards']
            for r, c in hand_counts.items():
                if r == 13: continue
                if state.is_valid_move(state.turn_index, r, c): possible_plays.append({'rank': r, 'count': c, 'jokers_used': 0, 'is_start': is_start})
            if num_jokers > 0:
                for r, c in hand_counts.items():
                    if r == 13: continue
                    for j in range(1, num_jokers + 1):
                        if state.is_valid_move(state.turn_index, r, c + j): possible_plays.append({'rank': r, 'count': c + j, 'jokers_used': j, 'is_start': is_start})
            if num_jokers > 0:
                if state.is_valid_move(state.turn_index, 13, num_jokers): possible_plays.append({'rank': 13, 'count': num_jokers, 'jokers_used': num_jokers, 'is_start': is_start})
                if num_jokers > 1 and state.is_valid_move(state.turn_index, 13, 1): possible_plays.append({'rank': 13, 'count': 1, 'jokers_used': 1, 'is_start': is_start})

            if not possible_plays:
                state.player_pass(state.turn_index)
            else:
                best_play = None
                if style == 'aggressive':
                    possible_plays.sort(key=lambda p: (p['jokers_used'], -p['count'] if p['is_start'] else 0, p['rank']))
                elif style == 'defensive':
                    possible_plays.sort(key=lambda p: (p['jokers_used'] * 10, p['rank'], -p['count']))
                else: # balanced
                    possible_plays.sort(key=lambda p: (p['jokers_used'], p['rank']))
                best_play = possible_plays[0]
                state.play_cards(state.turn_index, best_play['rank'], best_play['count'])
        self.update_ui()
    
    def auto_pass_human(self, dt):
        state = self.game_state
        if not state.game_over and state.turn_index == 0 and 0 in state.passed_in_round:
            state.game_log.append("You already passed. Auto-passing.")
            state.player_pass(0)
            self.update_ui()
    
    def update_ui(self):
        state = self.game_state
        if state.game_over:
            self.show_game_over_screen()
            return
            
        hand = state.players[0].hand
        self.player_hand_widget.update_hand(hand, self.selected_card_indices)
        self.table_widget.update_table(state.table_cards['cards'])
        self.other_players_widget.update_players(state.players, state.turn_index, state.round_lead_index, state.passed_in_round)
        self.log_widget.update_log(state.game_log)
        
        current_player = state.get_current_player()
        if not state.game_over:
            if current_player.is_ai:
                delay = 0.5 if state.turn_index in state.passed_in_round else 1
                Clock.schedule_once(self.run_ai_turn, delay)
            else:
                if state.turn_index in state.passed_in_round:
                    Clock.schedule_once(self.auto_pass_human, 0.5)

    def show_game_over_screen(self):
        winner_name = self.game_state.players[self.game_state.winner_index].name
        game_over_layout = BoxLayout(orientation='vertical', spacing=20, padding=50)
        winner_label = Label(text=f"{winner_name} is the Winner!", font_size='32sp', color=(0.5, 1, 0.5, 1))
        restart_button = Button(text="Play Again", font_size='24sp', size_hint=(0.5, 0.2), pos_hint={'center_x': 0.5})
        restart_button.bind(on_press=self.go_to_setup_screen)
        game_over_layout.add_widget(Label(size_hint_y=0.3))
        game_over_layout.add_widget(winner_label)
        game_over_layout.add_widget(restart_button)
        game_over_layout.add_widget(Label(size_hint_y=0.3))
        self.main_container.clear_widgets()
        self.main_container.add_widget(game_over_layout)

if __name__ == '__main__':
    DalmutiApp().run()

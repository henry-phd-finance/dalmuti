// =======================================================================
// HTML ID CHECKLIST
// 이 스크립트가 작동하려면 index.html 파일에 아래 ID들이 모두 있어야 합니다.
// 
// --- Screens ---
// #setup-screen
// #main-game-screen
// #game-over-screen
//
// --- Setup Screen Elements ---
// #player-count-display
// #minus-player-btn
// #plus-player-btn
// #ai-styles-container
// #start-game-btn
//
// --- Main Game Elements ---
// #log-content
// #other-players-area
// #table-area
// #player-hand-area
// #submit-btn
// #pass-btn
//
// --- Game Over Elements ---
// #winner-text
// #play-again-btn
// =======================================================================

document.addEventListener('DOMContentLoaded', () => {
    // --- 화면 요소 ---
    const setupScreen = document.getElementById('setup-screen');
    const mainGameScreen = document.getElementById('main-game-screen');
    const gameOverScreen = document.getElementById('game-over-screen');
    const winnerText = document.getElementById('winner-text');
    const playAgainBtn = document.getElementById('play-again-btn');

    // --- 설정 화면 요소 ---
    const playerCountDisplay = document.getElementById('player-count-display');
    const minusPlayerBtn = document.getElementById('minus-player-btn');
    const plusPlayerBtn = document.getElementById('plus-player-btn');
    const aiStylesContainer = document.getElementById('ai-styles-container');
    const startGameBtn = document.getElementById('start-game-btn');
    startGameBtn.style.color = 'black';
    playAgainBtn.style.color = 'black';
    // --- 메인 게임 화면 요소 ---
    const logContent = document.getElementById('log-content');
    const otherPlayersArea = document.getElementById('other-players-area');
    const tableArea = document.getElementById('table-area');
    const playerHandArea = document.getElementById('player-hand-area');
    const submitBtn = document.getElementById('submit-btn');
    const passBtn = document.getElementById('pass-btn');

    // --- 게임 상태 변수 ---
    let playerCount = 4;
    const aiStyles = ['mcts', 'balanced', 'aggressive', 'defensive'];
    let selectedAiStyles = [0, 0, 0, 0, 0, 1, 2];
    let gameState = null;
    let selectedCards = { indices: [], base_rank: null };

    const CARD_RANK_COLORS = [
        null, '#e63946', '#f4a261', '#e9c46a', '#a8dadc', '#457b9d', '#1d3557',
        '#a2d2ff', '#6a4c93', '#ff8282', '#ffbe0b', '#f72585', '#8338ec', '#505050'
    ];

    // =========================================
    // 게임 로직 클래스 (GameState, Player)
    // =========================================
    class Player {
        constructor(name, isAi = false, style = 'balanced') {
            this.name = name; this.isAi = isAi; this.style = style; this.hand = [];
        }
        sortHand() { this.hand.sort((a, b) => a - b); }
    }

    class GameState {
        /**
         * @param {string[]} playerStyles - 플레이어 스타일 목록
         * @param {boolean} isClone - 복제용으로 생성되는지 여부
         */
        constructor(playerStyles, isClone = false) {
            // 복제용으로 생성될 때는 초기화 로직을 건너뜁니다.
            if (isClone) {
                return;
            }

            this.players = [];
            const isHumanInGame = playerStyles.includes("You");
            playerStyles.forEach((style, i) => {
                const isAi = !isHumanInGame || style !== "You";
                const name = isAi ? `AI ${isHumanInGame ? i : i + 1}` : "You";
                this.players.push(new Player(name, isAi, style));
            });
            this.numPlayers = this.players.length;
            this.turnIndex = 0; this.roundLeadIndex = 0; this.tableCards = { cards: [], effectiveRank: 0 };
            this.passedInRound = new Set(); this.consecutivePasses = 0; this.gameOver = false;
            this.winnerIndex = -1; this.gameLog = [];
            this._setupDeckAndDeal();
        }

        _setupDeckAndDeal() {
            let deck = [];
            for (let i = 1; i <= 12; i++) { for (let j = 0; j < i; j++) deck.push(i); }
            deck.push(13, 13);
            for (let i = deck.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [deck[i], deck[j]] = [deck[j], deck[i]];
            }
            deck.forEach((card, i) => this.players[i % this.numPlayers].hand.push(card));
            this.players.forEach(p => p.sortHand());
            this.turnIndex = this.roundLeadIndex = Math.floor(Math.random() * this.numPlayers);
            this.log("--- New Game Started ---");
            this.log(`First turn: ${this.players[this.turnIndex].name}`);
        }
        
        log(message) { this.gameLog.push(message); }
        getCurrentPlayer() { return this.players[this.turnIndex]; }

        clone() {
            const clonedState = new GameState([], true); // 비어있는 객체 생성
            clonedState.numPlayers = this.numPlayers;
            clonedState.players = JSON.parse(JSON.stringify(this.players));
            clonedState.turnIndex = this.turnIndex;
            clonedState.roundLeadIndex = this.roundLeadIndex;
            clonedState.tableCards = JSON.parse(JSON.stringify(this.tableCards));
            clonedState.passedInRound = new Set(this.passedInRound);
            clonedState.consecutivePasses = this.consecutivePasses;
            clonedState.gameOver = this.gameOver;
            clonedState.winnerIndex = this.winnerIndex;
            clonedState.gameLog = [];
            return clonedState;
        }

        get_possible_moves() {
            if (this.passedInRound.has(this.turnIndex)) return ["pass"];
            const moves = [];
            const player = this.players[this.turnIndex];
            const handCounts = player.hand.reduce((acc, card) => { acc[card] = (acc[card] || 0) + 1; return acc; }, {});
            const numJokers = handCounts[13] || 0;
            for (let rankToPlay = 1; rankToPlay <= 13; rankToPlay++) {
                const nativeCount = handCounts[rankToPlay] || 0;
                const maxCount = rankToPlay === 13 ? numJokers : nativeCount + numJokers;
                for (let countToPlay = 1; countToPlay <= maxCount; countToPlay++) {
                    if (this.is_valid_move(this.turnIndex, rankToPlay, countToPlay)) {
                        moves.push({ rank: rankToPlay, count: countToPlay });
                    }
                }
            }
            moves.push("pass");
            return moves;
        }

        make_move(move) {
            const newState = this.clone();
            if (move === "pass") {
                newState.player_pass(newState.turnIndex);
            } else {
                newState.play_cards(newState.turnIndex, move.rank, move.count);
            }
            return newState;
        }

        is_valid_move(playerIndex, rank, count) {
            const player = this.players[playerIndex];
            if (this.passedInRound.has(playerIndex)) return false;
            const handCounts = player.hand.reduce((acc, card) => { acc[card] = (acc[card] || 0) + 1; return acc; }, {});
            const numJokers = handCounts[13] || 0;
            const numNative = handCounts[rank] || 0;
            if (rank === 13) { if (numJokers < count) return false; } 
            else { if (numNative + numJokers < count) return false; }
            if (this.tableCards.cards.length === 0) return true;
            return count === this.tableCards.cards.length && rank < this.tableCards.effectiveRank;
        }

        play_cards(playerIndex, rank, count) {
            const player = this.players[playerIndex];
            const handCounts = player.hand.reduce((acc, card) => { acc[card] = (acc[card] || 0) + 1; return acc; }, {});
            const nativeAvailable = handCounts[rank] || 0;
            const jokersToUse = Math.max(0, count - nativeAvailable);
            const nativeToUse = count - jokersToUse;
            for (let i = 0; i < nativeToUse; i++) player.hand.splice(player.hand.indexOf(rank), 1);
            for (let i = 0; i < jokersToUse; i++) player.hand.splice(player.hand.indexOf(13), 1);
            
            this.tableCards = { cards: Array(nativeToUse).fill(rank).concat(Array(jokersToUse).fill(13)), effectiveRank: rank };
            this.log(`${player.name} plays ${count}x card ${rank} (eff).`);
            
            this.consecutivePasses = 0;
            this.roundLeadIndex = playerIndex;
            // --- 핵심 수정: 카드를 내면 패스 기록을 초기화하여 모두가 다시 플레이할 수 있게 합니다. ---
            this.passedInRound.clear();

            if (player.hand.length === 0) {
                this.gameOver = true;
                this.winnerIndex = playerIndex;
                this.log(`🎉 ${player.name} wins the game! 🎉`);
                return;
            }
            this.advance_turn();
        }

        player_pass(playerIndex) {
            const player = this.players[playerIndex];
            // "auto-passes" 로그는 processNextTurn에서 처리하므로, 여기서는 일반 패스만 기록합니다.
            if (!this.passedInRound.has(playerIndex)) {
                 this.log(`${player.name} passes.`);
            }
            this.passedInRound.add(playerIndex);
            this.consecutivePasses++;

            // 더 안정적인 새 라운드 시작 조건:
            // 카드를 가진 플레이어 중 패스하지 않은 사람이 1명 이하일 때 새 라운드를 시작합니다.
            const activePlayersWithCards = this.players.filter(p => p.hand.length > 0).length;
            if (activePlayersWithCards - this.passedInRound.size <= 1) {
                this.log(`--- New round starts ---`);
                this.tableCards = { cards: [], effectiveRank: 0 };
                this.consecutivePasses = 0;
                this.passedInRound.clear();
                this.turnIndex = this.roundLeadIndex;
                if (this.players[this.turnIndex].hand.length === 0) {
                    this.advance_turn();
                }
            } else {
                this.advance_turn();
            }
        }
        
        advance_turn() {
            if (this.gameOver) return;
            do { this.turnIndex = (this.turnIndex + 1) % this.numPlayers; } 
            while (this.players[this.turnIndex].hand.length === 0);
        }
    }

    // =========================================
    // UI 렌더링 함수
    // =========================================
    function createCardElement(rank, isSelected = false) {
        const card = document.createElement('div');
        card.className = 'card';
        if (isSelected) card.classList.add('selected');
        card.style.backgroundColor = CARD_RANK_COLORS[rank];
        card.style.display = 'block'; 
        const numberSpan = document.createElement('span');
        numberSpan.textContent = rank === 13 ? 'J' : rank;
        numberSpan.style.position = 'absolute';
        numberSpan.style.top = '3px';
        numberSpan.style.left = '5px';
        numberSpan.style.fontSize = '16px';
        numberSpan.style.fontWeight = 'bold';
        numberSpan.style.color = 'white';
        numberSpan.style.textShadow = '1px 1px 2px rgba(0,0,0,0.8)';
        card.appendChild(numberSpan);
        return card;
    }

    function updateUI() {
        if (!gameState) return;

        if (gameState.gameOver) {
            mainGameScreen.classList.remove('active');
            gameOverScreen.classList.add('active');
            winnerText.textContent = `${gameState.players[gameState.winnerIndex].name} wins!`;
            return;
        }

        logContent.innerHTML = gameState.gameLog.slice().reverse().map(line => `<p>${line}</p>`).join('');

        const myPlayer = gameState.players.find(p => !p.isAi);
        playerHandArea.innerHTML = '';
        if(myPlayer) {
            const hand = myPlayer.hand;
            const cardCount = hand.length;
            const cardWidth = 45;
            const overlap = Math.min(28, playerHandArea.offsetWidth / (cardCount + 1));
            const isMultiLine = cardCount > 15;
            const cardsInRow1 = isMultiLine ? Math.ceil(cardCount / 2) : cardCount;
            const cardsInRow2 = isMultiLine ? cardCount - cardsInRow1 : 0;
            const totalWidth1 = cardWidth + (cardsInRow1 - 1) * overlap;
            const startX1 = (playerHandArea.offsetWidth - totalWidth1) / 2;
            
            if(isMultiLine) {
                const totalWidth2 = cardWidth + (cardsInRow2 - 1) * overlap;
                const startX2 = (playerHandArea.offsetWidth - totalWidth2) / 2;
                 for (let i = 0; i < cardsInRow2; i++) {
                    const handIndex = cardsInRow1 + i;
                    const rank = hand[handIndex];
                    const isSelected = selectedCards.indices.includes(handIndex);
                    const cardElement = createCardElement(rank, isSelected);
                    cardElement.dataset.handIndex = handIndex;
                    cardElement.style.left = `${startX2 + i * overlap}px`;
                    cardElement.style.top = '55%';
                    cardElement.style.zIndex = 20 + i;
                    playerHandArea.appendChild(cardElement);
                }
            }
            for (let i = 0; i < cardsInRow1; i++) {
                 const handIndex = i;
                 const rank = hand[handIndex];
                 const isSelected = selectedCards.indices.includes(handIndex);
                 const cardElement = createCardElement(rank, isSelected);
                 cardElement.dataset.handIndex = handIndex;
                 cardElement.style.left = `${startX1 + i * overlap}px`;
                 cardElement.style.top = isMultiLine ? '15%' : '50%';
                 cardElement.style.zIndex = i;
                 playerHandArea.appendChild(cardElement);
            }
        }

        otherPlayersArea.innerHTML = '';
        gameState.players.forEach((player, index) => {
            if (!player.isAi) return;
            const playerInfo = document.createElement('div');
            playerInfo.className = 'player-info';
            let status = '';
            if(index === gameState.roundLeadIndex) status += ' ✔';
            if(gameState.passedInRound.has(index)) status += ' (Pass)';
            playerInfo.textContent = `${player.name} (${player.style}): ${player.hand.length} cards ${status}`;
            if(index === gameState.turnIndex) playerInfo.classList.add('current-turn');
            if(gameState.passedInRound.has(index)) playerInfo.classList.add('player-passed');
            otherPlayersArea.appendChild(playerInfo);
        });
        
        tableArea.innerHTML = '';
        const tableCards = gameState.tableCards.cards;
        const tableCardCount = tableCards.length;
        if (tableCardCount > 0) {
            const tableCardWidth = 45;
            const tableOverlap = 22;
            const totalTableWidth = tableCardWidth + (tableCardCount - 1) * tableOverlap;
            const startTableX = (tableArea.offsetWidth - totalTableWidth) / 2;

            tableCards.forEach((rank, i) => {
                const cardElement = createCardElement(rank);
                cardElement.style.position = 'absolute';
                cardElement.style.left = `${startTableX + i * tableOverlap}px`;
                tableArea.appendChild(cardElement);
            });
        }
        
        const myPlayerIndex = myPlayer ? gameState.players.indexOf(myPlayer) : -1;
        const isMyActualTurn = myPlayer && gameState.turnIndex === myPlayerIndex;
        const hasPassedThisRound = myPlayer && gameState.passedInRound.has(myPlayerIndex);

        submitBtn.disabled = !isMyActualTurn || hasPassedThisRound;
        passBtn.disabled = !isMyActualTurn;
    }

    // =========================================
    // 게임 진행 로직
    // =========================================
    function processNextTurn() {
        if (!gameState || gameState.gameOver) {
            updateUI(); 
            return;
        }

        const currentPlayer = gameState.getCurrentPlayer();
        
        // 현재 플레이어가 이미 패스한 경우, 자동으로 턴을 넘깁니다.
        if (gameState.passedInRound.has(gameState.turnIndex)) {
            gameState.log(`${currentPlayer.name} auto-passes.`);
            gameState.player_pass(gameState.turnIndex); // 패스 규칙은 pass 함수에 위임
            updateUI();
            setTimeout(processNextTurn, 500); // 다음 턴으로 부드럽게 넘어감
            return;
        }
        
        // AI의 턴일 경우 (패스하지 않았을 때)
        if (currentPlayer.isAi) {
            gameState.log(`${currentPlayer.name} is thinking...`);
            updateLogsOnly();
            setTimeout(runAiTurn, 1200);
        }
        // 당신의 턴일 경우, 이 함수는 아무것도 하지 않고 당신의 입력을 기다립니다.
    }
    
    function updateLogsOnly() {
        logContent.innerHTML = gameState.gameLog.slice().reverse().map(line => `<p>${line}</p>`).join('');
    }
    
        function runAiTurn() {
        if (!gameState || gameState.gameOver || !gameState.getCurrentPlayer().isAi) return;
        
        gameState.gameLog.pop(); // "thinking..." 로그 제거

        const player = gameState.getCurrentPlayer();
        const playerIndex = gameState.turnIndex;
        const style = player.style;
        let best_play;

        if (style === 'mcts') {
            const mcts = new MCTS_AI({ iterations: 1000 });
            best_play = mcts.find_best_move(gameState);
        } else {
            const handCounts = player.hand.reduce((acc, card) => { acc[card] = (acc[card] || 0) + 1; return acc; }, {});
            const numJokers = handCounts[13] || 0;
            const is_start_of_round = gameState.tableCards.cards.length === 0;
            let possible_plays = [];
            
            for (let r in handCounts) {
                const rank = parseInt(r);
                if (rank === 13) continue;
                const count = handCounts[rank];
                if (gameState.is_valid_move(gameState.turnIndex, rank, count)) possible_plays.push({ rank, count, jokersUsed: 0, is_start: is_start_of_round });
                if (numJokers > 0) {
                    for (let j = 1; j <= numJokers; j++) {
                        if (gameState.is_valid_move(gameState.turnIndex, rank, count + j)) possible_plays.push({ rank, count: count + j, jokersUsed: j, is_start: is_start_of_round });
                    }
                }
            }
            if (numJokers > 0 && gameState.is_valid_move(gameState.turnIndex, 13, numJokers)) {
                possible_plays.push({ rank: 13, count: numJokers, jokersUsed: numJokers, is_start: is_start_of_round });
            }

            if (possible_plays.length === 0) {
                best_play = "pass";
            } else {
                if (player.style === 'aggressive') {
                    possible_plays.sort((a, b) => (a.jokersUsed - b.jokersUsed) || (b.is_start ? b.count - a.count : a.rank - b.rank));
                } else if (player.style === 'defensive') {
                    possible_plays.sort((a, b) => (a.jokersUsed * 10 - b.jokersUsed * 10) || (b.rank - a.rank));
                } else { // balanced
                    possible_plays.sort((a, b) => (a.jokersUsed - b.jokersUsed) || (b.rank - a.rank));
                }
                best_play = possible_plays[0];
            }
        }
        
        // --- 핵심 버그 수정: AI가 조커만 단독으로 내는 경우, 등급을 13으로 강제 ---
        if (best_play !== "pass" && best_play.jokersUsed === best_play.count) {
            best_play.rank = 13;
        }
        // --- 수정 종료 ---

        if (best_play === "pass") {
            gameState.player_pass(gameState.turnIndex);
        } else {
            gameState.play_cards(gameState.turnIndex, best_play.rank, best_play.count);
        }
        updateUI();
        processNextTurn();
    }

    
    // =========================================
    // 이벤트 리스너
    // =========================================
    function handleCardClick(handIndex) {
        const hand = gameState.players[0].hand;
        const clicked_rank = hand[handIndex];
        
        if (selectedCards.indices.includes(handIndex)) {
            selectedCards.indices = selectedCards.indices.filter(i => i !== handIndex);
            if (selectedCards.indices.length === 0) {
                selectedCards.base_rank = null;
            } else {
                const remainingRanks = selectedCards.indices.map(i => hand[i]);
                if (remainingRanks.every(r => r === 13)) {
                    selectedCards.base_rank = 13;
                }
            }
        } else {
            const base_rank = selectedCards.base_rank;
            if (!base_rank) {
                selectedCards.indices.push(handIndex);
                selectedCards.base_rank = clicked_rank;
            } else if (clicked_rank === base_rank || clicked_rank === 13) {
                selectedCards.indices.push(handIndex);
            } else if (base_rank === 13) {
                selectedCards.indices.push(handIndex);
                selectedCards.base_rank = clicked_rank;
            } else {
                selectedCards.indices = [handIndex];
                selectedCards.base_rank = clicked_rank;
            }
        }
        updateUI();
    }
    playerHandArea.addEventListener('click', (e) => {
        const cardElement = e.target.closest('.card');
        if (cardElement) {
            const handIndex = parseInt(cardElement.dataset.handIndex);
            handleCardClick(handIndex);
        }
    });

    submitBtn.addEventListener('click', () => {
        if (selectedCards.indices.length === 0) return;
        const playerIndex = gameState.players.findIndex(p => !p.isAi);
        const rankToPlay = selectedCards.base_rank;
        const countToPlay = selectedCards.indices.length;
        if (gameState.is_valid_move(playerIndex, rankToPlay, countToPlay)) {
            gameState.play_cards(playerIndex, rankToPlay, countToPlay);
            selectedCards = { indices: [], base_rank: null };
            updateUI();
            processNextTurn();
        } else {
            alert("Invalid move!");
        }
    });

    passBtn.addEventListener('click', () => {
        const playerIndex = gameState.players.findIndex(p => !p.isAi);
        gameState.player_pass(playerIndex);
        selectedCards = { indices: [], base_rank: null };
        updateUI();
        processNextTurn();
    });
    
    startGameBtn.addEventListener('click', () => {
        const playerIndexOffset = 1;
        const finalPlayerStyles = ["You"];
        for(let i=0; i < playerCount - playerIndexOffset; i++) {
            finalPlayerStyles.push(aiStyles[selectedAiStyles[i]]);
        }
        gameState = new GameState(finalPlayerStyles);
        setupScreen.classList.remove('active');
        mainGameScreen.classList.add('active');
        updateUI();
        processNextTurn();
    });

    function updateSetupScreen() {
        playerCountDisplay.textContent = `${playerCount} Players`;
        minusPlayerBtn.disabled = playerCount <= 2;
        plusPlayerBtn.disabled = playerCount >= 8;
        aiStylesContainer.innerHTML = '';
        for (let i = 1; i < playerCount; i++) {
            const aiStyleSelector = document.createElement('div');
            aiStyleSelector.className = 'ai-style-selector';
            const currentStyleIndex = selectedAiStyles[i - 1];
            const currentStyle = aiStyles[currentStyleIndex];
            
            const label = document.createElement('span');
            label.textContent = `AI ${i}:`;
            
            const controls = document.createElement('div');
            
            const leftBtn = document.createElement('button');
            leftBtn.className = 'style-change-btn';
            leftBtn.dataset.aiIndex = i - 1;
            leftBtn.dataset.direction = '-1';
            leftBtn.textContent = '<';
            leftBtn.style.color = 'black';

            const styleDisplay = document.createElement('span');
            styleDisplay.className = 'ai-style-display';
            styleDisplay.textContent = currentStyle.charAt(0).toUpperCase() + currentStyle.slice(1);

            const rightBtn = document.createElement('button');
            rightBtn.className = 'style-change-btn';
            rightBtn.dataset.aiIndex = i - 1;
            rightBtn.dataset.direction = '1';
            rightBtn.textContent = '>';
            rightBtn.style.color = 'black';

            controls.appendChild(leftBtn);
            controls.appendChild(styleDisplay);
            controls.appendChild(rightBtn);

            aiStyleSelector.appendChild(label);
            aiStyleSelector.appendChild(controls);

            aiStylesContainer.appendChild(aiStyleSelector);
        }
    }
    
    aiStylesContainer.addEventListener('click', (e) => {
        if (e.target.classList.contains('style-change-btn')) {
            const aiIndex = parseInt(e.target.dataset.aiIndex);
            const direction = parseInt(e.target.dataset.direction);
            const newIndex = (selectedAiStyles[aiIndex] + direction + aiStyles.length) % aiStyles.length;
            selectedAiStyles[aiIndex] = newIndex;
            updateSetupScreen();
        }
    });

    minusPlayerBtn.style.color = 'black';
    plusPlayerBtn.style.color = 'black';

    minusPlayerBtn.addEventListener('click', () => { if (playerCount > 2) { playerCount--; updateSetupScreen(); } });
    plusPlayerBtn.addEventListener('click', () => { if (playerCount < 8) { playerCount++; updateSetupScreen(); } });
    playAgainBtn.addEventListener('click', () => {
        gameOverScreen.classList.remove('active');
        setupScreen.classList.add('active');
        gameState = null;
        updateSetupScreen();
    });

    updateSetupScreen();
});

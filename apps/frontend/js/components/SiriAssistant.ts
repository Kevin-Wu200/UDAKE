/**
 * Siri 智能助手悬浮球组件
 *
 * 特性：
 * - 桌面/移动端自由拖动
 * - 点击展开/收起交互面板
 * - 支持文字输入和语音输入
 * - 通过 API 与后端智能模块通信
 * - Apple 风格动效
 */

import type { APIService } from '../services/api/APIService';
import { Logger } from '../utils/Logger';

// --- 接口定义 ---

type SpeechRecognitionConstructor = new () => SpeechRecognition;

interface SpeechRecognition extends EventTarget {
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    onresult: ((event: SpeechRecognitionEvent) => void) | null;
    onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
    onend: (() => void) | null;
    start(): void;
    stop(): void;
}

interface SpeechRecognitionEvent extends Event {
    results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
    readonly length: number;
    item(index: number): SpeechRecognitionResult;
    [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
    readonly length: number;
    item(index: number): SpeechRecognitionAlternative;
    [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
    transcript: string;
    confidence: number;
}

interface SpeechRecognitionErrorEvent extends Event {
    error: string;
    message: string;
}

interface SiriResponse {
    success: boolean;
    intent: string;
    answer: string;
    retrieved_docs?: Array<{
        content: string;
        source: string;
        relevance_score: number;
        title?: string;
    }>;
    function_call?: {
        function: string;
        params: Record<string, unknown>;
        confidence: number;
        description: string;
        requires_confirmation: boolean;
    } | null;
    fallback: boolean;
    session_id: string;
    processing_time_ms: number;
}

interface ChatMessage {
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: number;
    function_call?: SiriResponse['function_call'];
}

/** 位置存储 key */
const POSITION_STORAGE_KEY = 'siri_assistant_position';

export class SiriAssistant {
    // --- 私有属性 ---
    private container: HTMLElement;
    private ball: HTMLElement;
    private panel: HTMLElement;
    private chatArea: HTMLElement;
    private inputArea: HTMLInputElement;
    private sendBtn: HTMLElement;
    private voiceBtn: HTMLElement;
    private closeBtn: HTMLElement;
    private badge: HTMLElement;

    private isDragging = false;
    private isPanelOpen = false;
    private isListening = false;
    private dragStart = { x: 0, y: 0 };
    private ballStart = { x: 0, y: 0 };
    private position = { x: 0, y: 0 };
    private sessionId: string | null = null;
    private messages: ChatMessage[] = [];
    private apiService: APIService | null = null;

    // 语音识别相关
    private recognition: SpeechRecognition | null = null;

    // 安全边界
    private readonly BALL_SIZE = 56;
    private readonly MARGIN = 12;

    constructor() {
        this.container = document.createElement('div');
        this.container.id = 'siri-assistant-container';

        this.ball = document.createElement('div');
        this.ball.id = 'siri-ball';
        this.ball.innerHTML = this._getBallIcon();
        this.ball.setAttribute('role', 'button');
        this.ball.setAttribute('aria-label', '打开智能助手');
        this.ball.setAttribute('title', 'UDAKE 小U');

        this.panel = document.createElement('div');
        this.panel.id = 'siri-panel';
        this.panel.setAttribute('aria-hidden', 'true');

        this.chatArea = document.createElement('div');
        this.chatArea.id = 'siri-chat-area';

        this.inputArea = document.createElement('input');
        this.inputArea.type = 'text';
        this.inputArea.id = 'siri-input';
        this.inputArea.placeholder = '输入问题或指令...';
        this.inputArea.setAttribute('aria-label', '输入问题或指令');

        this.sendBtn = document.createElement('button');
        this.sendBtn.id = 'siri-send-btn';
        this.sendBtn.innerHTML = '➤';
        this.sendBtn.setAttribute('aria-label', '发送');
        this.sendBtn.title = '发送';

        this.voiceBtn = document.createElement('button');
        this.voiceBtn.id = 'siri-voice-btn';
        this.voiceBtn.innerHTML = '🎤';
        this.voiceBtn.setAttribute('aria-label', '语音输入');
        this.voiceBtn.title = '语音输入';

        this.closeBtn = document.createElement('button');
        this.closeBtn.id = 'siri-close-btn';
        this.closeBtn.innerHTML = '✕';
        this.closeBtn.setAttribute('aria-label', '关闭');
        this.closeBtn.title = '关闭';

        this.badge = document.createElement('div');
        this.badge.id = 'siri-badge';
        this.badge.style.display = 'none';
    }

    // --- 公共方法 ---

    /**
     * 初始化助手组件
     */
    init(apiService?: APIService): void {
        this.apiService = apiService || null;

        document.body.appendChild(this.container);
        this.container.appendChild(this.ball);
        this.container.appendChild(this.badge);

        // 构建面板
        this._buildPanel();

        // 加载保存的位置
        this._loadPosition();

        // 绑定事件
        this._bindBallEvents();
        this._bindPanelEvents();
        this._bindKeyboardEvents();

        // 初始化语音识别
        this._initSpeechRecognition();

        // 设置初始位置
        this._updateBallPosition();

        Logger.info('SiriAssistant', '小U 助手组件已初始化');
    }

    /**
     * 销毁组件
     */
    destroy(): void {
        this.container.remove();
        Logger.info('SiriAssistant', '小U 助手组件已销毁');
    }

    /**
     * 打开面板
     */
    openPanel(): void {
        if (this.isPanelOpen) return;
        this.isPanelOpen = true;
        this.panel.setAttribute('aria-hidden', 'false');
        this.ball.classList.add('siri-ball-active');
        document.body.appendChild(this.panel);
        // 添加欢迎消息
        if (this.messages.length === 0) {
            this._addMessage('assistant', '您好！我是 UDAKE 小U 🎯\n\n我可以帮您：\n• 解答技术问题和操作指南\n• 执行系统功能\n• 检索文档知识\n\n请问有什么可以帮您的？');
        }
        setTimeout(() => this.inputArea.focus(), 300);
    }

    /**
     * 关闭面板
     */
    closePanel(): void {
        if (!this.isPanelOpen) return;
        this.isPanelOpen = false;
        this.panel.setAttribute('aria-hidden', 'true');
        this.ball.classList.remove('siri-ball-active');
        if (this.panel.parentElement) {
            this.panel.parentElement.removeChild(this.panel);
        }
    }

    // --- 私有方法 ---

    private _getBallIcon(): string {
        return `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M8 14s1.5 2 4 2 4-2 4-2"></path>
            <line x1="9" y1="9" x2="9.01" y2="9"></line>
            <line x1="15" y1="9" x2="15.01" y2="9"></line>
        </svg>`;
    }

    private _buildPanel(): void {
        this.panel.innerHTML = '';

        // 头部
        const header = document.createElement('div');
        header.id = 'siri-panel-header';
        header.innerHTML = `
            <div class="siri-panel-title">
                <span class="siri-panel-icon">🤖</span>
                <span>UDAKE 小U</span>
            </div>
        `;
        header.appendChild(this.closeBtn);

        // 聊天区域
        this.chatArea.id = 'siri-chat-area';

        // 文档引用区域
        const docRef = document.createElement('div');
        docRef.id = 'siri-doc-ref';
        docRef.style.display = 'none';

        // 功能调用确认区域
        const funcConfirm = document.createElement('div');
        funcConfirm.id = 'siri-func-confirm';
        funcConfirm.style.display = 'none';

        // 输入区域
        const inputContainer = document.createElement('div');
        inputContainer.id = 'siri-input-container';
        inputContainer.appendChild(this.voiceBtn);
        inputContainer.appendChild(this.inputArea);
        inputContainer.appendChild(this.sendBtn);

        // 底部状态栏
        const statusBar = document.createElement('div');
        statusBar.id = 'siri-status-bar';
        statusBar.textContent = 'UDAKE 智能助手 · 基于 Qwen3:8b';

        this.panel.appendChild(header);
        this.panel.appendChild(this.chatArea);
        this.panel.appendChild(docRef);
        this.panel.appendChild(funcConfirm);
        this.panel.appendChild(inputContainer);
        this.panel.appendChild(statusBar);
    }

    private _bindBallEvents(): void {
        // 桌面端拖拽
        this.ball.addEventListener('mousedown', (e) => this._onDragStart(e as MouseEvent));
        document.addEventListener('mousemove', (e) => this._onDragMove(e as MouseEvent));
        document.addEventListener('mouseup', (e) => this._onDragEnd(e as MouseEvent));

        // 点击打开/关闭面板（非拖拽情况下）
        this.ball.addEventListener('click', () => {
            if (this.isDragging) return;
            this.isPanelOpen ? this.closePanel() : this.openPanel();
        });

        // 移动端拖拽
        this.ball.addEventListener('touchstart', (e) => this._onTouchStart(e as TouchEvent), { passive: false });
        document.addEventListener('touchmove', (e) => this._onTouchMove(e as TouchEvent), { passive: false });
        document.addEventListener('touchend', (e) => this._onTouchEnd(e as TouchEvent));
    }

    private _bindPanelEvents(): void {
        this.closeBtn.addEventListener('click', () => this.closePanel());
        this.sendBtn.addEventListener('click', () => this._sendMessage());
        this.voiceBtn.addEventListener('click', () => this._toggleVoiceInput());
        this.inputArea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this._sendMessage();
            }
        });

        // 点击面板外部关闭 (通过全局事件处理)
        document.addEventListener('click', (e) => {
            if (this.isPanelOpen &&
                !this.panel.contains(e.target as Node) &&
                !this.ball.contains(e.target as Node)) {
                this.closePanel();
            }
        });
    }

    private _bindKeyboardEvents(): void {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K 快速打开助手
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                if (this.isPanelOpen) {
                    this.closePanel();
                } else {
                    this.openPanel();
                }
            }
            // Escape 关闭
            if (e.key === 'Escape' && this.isPanelOpen) {
                this.closePanel();
            }
        });
    }

    // --- 拖拽处理 ---

    private _onDragStart(e: MouseEvent): void {
        if (this.isPanelOpen) return;
        this.isDragging = true;
        this.dragStart = { x: e.clientX, y: e.clientY };
        this.ballStart = { ...this.position };
        this.ball.style.transition = 'none';
        e.preventDefault();
    }

    private _onDragMove(e: MouseEvent): void {
        if (!this.isDragging) return;
        const dx = e.clientX - this.dragStart.x;
        const dy = e.clientY - this.dragStart.y;
        this.position = {
            x: this.ballStart.x + dx,
            y: this.ballStart.y + dy,
        };
        this._clampPosition();
        this._updateBallPosition();
    }

    private _onDragEnd(_e: MouseEvent): void {
        if (!this.isDragging) return;
        this.isDragging = false;
        this.ball.style.transition = '';
        this._snapToEdge();
        this._savePosition();
    }

    private _onTouchStart(e: TouchEvent): void {
        if (this.isPanelOpen) return;
        const touch = e.touches[0];
        this.isDragging = true;
        this.dragStart = { x: touch.clientX, y: touch.clientY };
        this.ballStart = { ...this.position };
        this.ball.style.transition = 'none';
        e.preventDefault();
    }

    private _onTouchMove(e: TouchEvent): void {
        if (!this.isDragging) return;
        const touch = e.touches[0];
        const dx = touch.clientX - this.dragStart.x;
        const dy = touch.clientY - this.dragStart.y;
        this.position = {
            x: this.ballStart.x + dx,
            y: this.ballStart.y + dy,
        };
        this._clampPosition();
        this._updateBallPosition();
        e.preventDefault();
    }

    private _onTouchEnd(_e: TouchEvent): void {
        if (!this.isDragging) return;
        this.isDragging = false;
        this.ball.style.transition = '';
        this._snapToEdge();
        this._savePosition();
    }

    private _clampPosition(): void {
        const maxX = window.innerWidth - this.BALL_SIZE - this.MARGIN;
        const maxY = window.innerHeight - this.BALL_SIZE - this.MARGIN;
        this.position.x = Math.max(this.MARGIN, Math.min(this.position.x, maxX));
        this.position.y = Math.max(this.MARGIN, Math.min(this.position.y, maxY));
    }

    private _snapToEdge(): void {
        const midX = window.innerWidth / 2;
        if (this.position.x + this.BALL_SIZE / 2 < midX) {
            this.position.x = this.MARGIN;
        } else {
            this.position.x = window.innerWidth - this.BALL_SIZE - this.MARGIN;
        }
    }

    private _updateBallPosition(): void {
        this.ball.style.left = `${this.position.x}px`;
        this.ball.style.top = `${this.position.y}px`;
    }

    private _savePosition(): void {
        try {
            localStorage.setItem(POSITION_STORAGE_KEY, JSON.stringify(this.position));
        } catch { /* 忽略存储错误 */ }
    }

    private _loadPosition(): void {
        try {
            const saved = localStorage.getItem(POSITION_STORAGE_KEY);
            if (saved) {
                const parsed = JSON.parse(saved);
                this.position = { x: parsed.x || 0, y: parsed.y || 0 };
            }
        } catch { /* 使用默认位置 */ }

        // 默认位置：右下角
        if (!this.position.x && !this.position.y) {
            this.position = {
                x: window.innerWidth - this.BALL_SIZE - this.MARGIN,
                y: window.innerHeight - this.BALL_SIZE - this.MARGIN - 80,
            };
        }
        this._clampPosition();
    }

    // --- 消息处理 ---

    private async _sendMessage(): Promise<void> {
        const text = this.inputArea.value.trim();
        if (!text) return;

        this.inputArea.value = '';
        this._addMessage('user', text);
        this._setTyping(true);

        try {
            const response = await this._callSiriAPI(text);
            this._handleResponse(response);
        } catch (error) {
            Logger.error('SiriAssistant', '小U API 调用失败', error);
            this._addMessage('assistant', '抱歉，助手服务暂时不可用。请检查网络连接和后端服务状态。');
        } finally {
            this._setTyping(false);
        }
    }

    private async _callSiriAPI(query: string): Promise<SiriResponse> {
        // 尝试通过 APIService 调用
        if (this.apiService) {
            const response = await this.apiService.request<SiriResponse>('/api/siri/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    session_id: this.sessionId,
                    voice_input: false,
                }),
            });
            this.sessionId = response.session_id;
            return response;
        }

        // 回退：直接 fetch
        const baseURL = this._getBaseURL();
        const response = await fetch(`${baseURL}/api/siri/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                session_id: this.sessionId,
                voice_input: false,
            }),
        });
        const data = await response.json() as SiriResponse;
        this.sessionId = data.session_id;
        return data;
    }

    private _getBaseURL(): string {
        // 尝试从 APIService 获取
        if (this.apiService?.baseURL) {
            return this.apiService.baseURL;
        }
        // 回退：从当前页面 URL 推断
        const { protocol, hostname } = window.location;
        const port = '8000'; // 默认后端端口
        return `${protocol}//${hostname}:${port}`;
    }

    private _handleResponse(response: SiriResponse): void {
        // 添加回答消息
        this._addMessage('assistant', response.answer);

        // 显示功能调用确认
        const funcConfirm = document.getElementById('siri-func-confirm');
        if (funcConfirm && response.function_call) {
            funcConfirm.style.display = 'block';
            funcConfirm.innerHTML = `
                <div class="func-confirm-inner">
                    <p>🔧 ${response.function_call.description}</p>
                    ${response.function_call.requires_confirmation ? `
                    <div class="func-confirm-actions">
                        <button class="func-confirm-yes" onclick="this.closest('#siri-func-confirm').style.display='none'">✅ 确认执行</button>
                        <button class="func-confirm-no" onclick="this.closest('#siri-func-confirm').style.display='none'">❌ 取消</button>
                    </div>
                    ` : ''}
                </div>
            `;
            setTimeout(() => {
                if (funcConfirm) funcConfirm.style.display = 'none';
            }, 10000);
        }

        // 显示文档引用
        if (response.retrieved_docs && response.retrieved_docs.length > 0) {
            const docRef = document.getElementById('siri-doc-ref');
            if (docRef) {
                docRef.style.display = 'block';
                const sources = response.retrieved_docs
                    .slice(0, 3)
                    .map(d => `📄 ${d.source}`)
                    .join(' · ');
                docRef.innerHTML = `<span class="doc-ref-text">参考: ${sources}</span>`;
                setTimeout(() => {
                    if (docRef) docRef.style.display = 'none';
                }, 8000);
            }
        }
    }

    private _addMessage(role: 'user' | 'assistant' | 'system', content: string, function_call?: SiriResponse['function_call']): void {
        const message: ChatMessage = {
            role,
            content,
            timestamp: Date.now(),
            function_call,
        };
        this.messages.push(message);

        const msgEl = document.createElement('div');
        msgEl.className = `siri-message siri-message-${role}`;

        if (role === 'user') {
            msgEl.innerHTML = `<div class="siri-message-bubble">${this._escapeHtml(content)}</div>`;
        } else {
            msgEl.innerHTML = `
                <div class="siri-message-avatar">🤖</div>
                <div class="siri-message-bubble">${this._formatMessage(content)}</div>
            `;
        }

        this.chatArea.appendChild(msgEl);
        this.chatArea.scrollTop = this.chatArea.scrollHeight;
    }

    private _setTyping(typing: boolean): void {
        this.sendBtn.classList.toggle('siri-sending', typing);
        this.sendBtn.innerHTML = typing ? '⏳' : '➤';
        this.inputArea.disabled = typing;
    }

    private _formatMessage(text: string): string {
        // 简单的 Markdown 转换
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    private _escapeHtml(text: string): string {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // --- 语音识别 ---

    private _initSpeechRecognition(): void {
        const speechWindow = window as Window & {
            SpeechRecognition?: SpeechRecognitionConstructor;
            webkitSpeechRecognition?: SpeechRecognitionConstructor;
        };
        const SpeechRecognitionCtor = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
        if (!SpeechRecognitionCtor) {
            this.voiceBtn.style.display = 'none';
            return;
        }

        this.recognition = new SpeechRecognitionCtor();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = 'zh-CN';

        this.recognition.onresult = (event: SpeechRecognitionEvent) => {
            const transcript = event.results[0][0].transcript;
            this.inputArea.value = transcript;
            this._stopListening();
            // 自动发送
            setTimeout(() => this._sendMessage(), 300);
        };

        this.recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
            Logger.warn('SiriAssistant', '语音识别错误', event.error);
            this._stopListening();
        };

        this.recognition.onend = () => {
            this._stopListening();
        };
    }

    private _toggleVoiceInput(): void {
        if (!this.recognition) return;

        if (this.isListening) {
            this._stopListening();
        } else {
            this._startListening();
        }
    }

    private _startListening(): void {
        if (!this.recognition || this.isListening) return;
        this.isListening = true;
        this.voiceBtn.classList.add('siri-listening');
        this.voiceBtn.innerHTML = '🔴';
        this.inputArea.placeholder = '正在聆听...';
        try {
            this.recognition.start();
        } catch {
            // 可能已经在识别中
        }
    }

    private _stopListening(): void {
        this.isListening = false;
        this.voiceBtn.classList.remove('siri-listening');
        this.voiceBtn.innerHTML = '🎤';
        this.inputArea.placeholder = '输入问题或指令...';
        try {
            this.recognition?.stop();
        } catch {
            // 可能已经停止
        }
    }
}

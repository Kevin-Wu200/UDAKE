export interface TimeSliderEvents {
    onTimeChange?: (timestamp: string, index: number) => void;
    onPlayStateChange?: (playing: boolean) => void;
    onSpeedChange?: (speed: number) => void;
}

export class TimeSlider {
    private readonly container: HTMLElement;
    private readonly events: TimeSliderEvents;
    private timeline: string[] = [];
    private currentIndex = 0;
    private playing = false;
    private speed = 1;
    private timer: number | null = null;

    constructor(container: HTMLElement, events: TimeSliderEvents = {}) {
        this.container = container;
        this.events = events;
        this.render();
        this.bindEvents();
    }

    setTimeline(timeline: string[]): void {
        this.timeline = timeline;
        this.currentIndex = 0;
        const slider = this.container.querySelector('#st-time-slider') as HTMLInputElement | null;
        if (slider) {
            slider.min = '0';
            slider.max = String(Math.max(0, timeline.length - 1));
            slider.value = '0';
            slider.disabled = timeline.length === 0;
        }
        this.updateCurrentTimeLabel();
    }

    setCurrentTime(index: number): void {
        if (this.timeline.length === 0) {
            return;
        }
        this.currentIndex = Math.max(0, Math.min(index, this.timeline.length - 1));
        const slider = this.container.querySelector('#st-time-slider') as HTMLInputElement | null;
        if (slider) {
            slider.value = String(this.currentIndex);
        }
        this.updateCurrentTimeLabel();
        this.emitTimeChange();
    }

    getCurrentTime(): string | null {
        return this.timeline[this.currentIndex] || null;
    }

    private render(): void {
        this.container.innerHTML = `
            <div class="st-time-slider-panel">
                <div class="st-time-slider-row">
                    <input id="st-time-slider" type="range" min="0" max="0" value="0" step="1" disabled>
                    <span id="st-time-current">--</span>
                </div>
                <div class="st-time-controls">
                    <button id="st-time-prev" type="button">◀◀</button>
                    <button id="st-time-play" type="button">▶</button>
                    <button id="st-time-next" type="button">▶▶</button>
                    <label>
                        速度
                        <select id="st-time-speed">
                            <option value="0.5">0.5x</option>
                            <option value="1" selected>1x</option>
                            <option value="2">2x</option>
                            <option value="4">4x</option>
                        </select>
                    </label>
                </div>
            </div>
        `;
    }

    private bindEvents(): void {
        const slider = this.container.querySelector('#st-time-slider') as HTMLInputElement | null;
        slider?.addEventListener('input', () => {
            this.setCurrentTime(Number(slider.value));
        });

        const playBtn = this.container.querySelector('#st-time-play') as HTMLButtonElement | null;
        playBtn?.addEventListener('click', () => this.togglePlay());

        this.container.querySelector('#st-time-prev')?.addEventListener('click', () => {
            this.setCurrentTime(this.currentIndex - 1);
        });

        this.container.querySelector('#st-time-next')?.addEventListener('click', () => {
            this.setCurrentTime(this.currentIndex + 1);
        });

        const speedSelect = this.container.querySelector('#st-time-speed') as HTMLSelectElement | null;
        speedSelect?.addEventListener('change', () => {
            this.speed = Number(speedSelect.value) || 1;
            this.events.onSpeedChange?.(this.speed);
            if (this.playing) {
                this.restartTimer();
            }
        });
    }

    private togglePlay(): void {
        this.playing = !this.playing;
        const playBtn = this.container.querySelector('#st-time-play') as HTMLButtonElement | null;
        if (playBtn) {
            playBtn.textContent = this.playing ? '暂停' : '▶';
        }

        if (this.playing) {
            this.restartTimer();
        } else {
            this.clearTimer();
        }

        this.events.onPlayStateChange?.(this.playing);
    }

    private restartTimer(): void {
        this.clearTimer();
        const interval = Math.max(120, 1000 / this.speed);
        this.timer = window.setInterval(() => {
            if (this.currentIndex >= this.timeline.length - 1) {
                this.togglePlay();
                return;
            }
            this.setCurrentTime(this.currentIndex + 1);
        }, interval);
    }

    private clearTimer(): void {
        if (this.timer !== null) {
            window.clearInterval(this.timer);
            this.timer = null;
        }
    }

    private updateCurrentTimeLabel(): void {
        const label = this.container.querySelector('#st-time-current') as HTMLElement | null;
        if (label) {
            label.textContent = this.timeline[this.currentIndex] || '--';
        }
    }

    private emitTimeChange(): void {
        const timestamp = this.timeline[this.currentIndex];
        if (timestamp) {
            this.events.onTimeChange?.(timestamp, this.currentIndex);
        }
    }

    destroy(): void {
        this.clearTimer();
        this.container.innerHTML = '';
    }
}

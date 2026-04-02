import { vi } from 'vitest';

export type CanvasMockContext = {
    clearRect: ReturnType<typeof vi.fn>;
    fillRect: ReturnType<typeof vi.fn>;
    beginPath: ReturnType<typeof vi.fn>;
    moveTo: ReturnType<typeof vi.fn>;
    lineTo: ReturnType<typeof vi.fn>;
    stroke: ReturnType<typeof vi.fn>;
    closePath: ReturnType<typeof vi.fn>;
    fill: ReturnType<typeof vi.fn>;
    arc: ReturnType<typeof vi.fn>;
    setLineDash: ReturnType<typeof vi.fn>;
    fillText: ReturnType<typeof vi.fn>;
    measureText: ReturnType<typeof vi.fn>;
    createLinearGradient: ReturnType<typeof vi.fn>;
    save: ReturnType<typeof vi.fn>;
    restore: ReturnType<typeof vi.fn>;
    translate: ReturnType<typeof vi.fn>;
    rotate: ReturnType<typeof vi.fn>;
    strokeStyle: string;
    fillStyle: string;
    lineWidth: number;
    font: string;
    textAlign: string;
    textBaseline: string;
    globalAlpha: number;
};

export function installCanvasMock() {
    const gradient = { addColorStop: vi.fn() };
    const ctx: CanvasMockContext = {
        clearRect: vi.fn(),
        fillRect: vi.fn(),
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        stroke: vi.fn(),
        closePath: vi.fn(),
        fill: vi.fn(),
        arc: vi.fn(),
        setLineDash: vi.fn(),
        fillText: vi.fn(),
        measureText: vi.fn(() => ({ width: 64 })),
        createLinearGradient: vi.fn(() => gradient),
        save: vi.fn(),
        restore: vi.fn(),
        translate: vi.fn(),
        rotate: vi.fn(),
        strokeStyle: '',
        fillStyle: '',
        lineWidth: 1,
        font: '',
        textAlign: 'left',
        textBaseline: 'alphabetic',
        globalAlpha: 1
    };

    const getContextSpy = vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => ctx as unknown as CanvasRenderingContext2D);
    const toDataURLSpy = vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,mock');

    return {
        ctx,
        restore: () => {
            getContextSpy.mockRestore();
            toDataURLSpy.mockRestore();
        }
    };
}

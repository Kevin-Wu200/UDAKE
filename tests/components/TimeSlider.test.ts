import { describe, expect, it, vi } from 'vitest';
import { TimeSlider } from '../../apps/frontend/js/components/TimeSlider';

describe('TimeSlider', () => {
    it('应在拖动后触发时间变更事件', () => {
        const host = document.createElement('div');
        const onTimeChange = vi.fn();
        const slider = new TimeSlider(host, { onTimeChange });
        slider.setTimeline(['2026-01-01', '2026-01-02', '2026-01-03']);

        const input = host.querySelector('#st-time-slider') as HTMLInputElement;
        input.value = '2';
        input.dispatchEvent(new Event('input'));

        expect(onTimeChange).toHaveBeenCalledWith('2026-01-03', 2);
        slider.destroy();
    });
});

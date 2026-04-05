import { describe, expect, it } from 'vitest';

import { TimeSlider } from '../js/components/TimeSlider';

describe('timeslider smoke', () => {
    it('should set timeline', () => {
        const container = document.createElement('div');
        const slider = new TimeSlider(container);
        slider.setTimeline(['2026-04-05T00:00:00Z']);
        expect(slider.getCurrentTime()).toBe('2026-04-05T00:00:00Z');
    });
});

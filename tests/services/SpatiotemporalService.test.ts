import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SpatiotemporalService } from '../../apps/frontend/js/services/SpatiotemporalService';

describe('SpatiotemporalService', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    it('应调用训练接口并返回数据', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ success: true, message: 'ok', data: { model_id: 'm1' } })
        }));

        const service = new SpatiotemporalService('/api/spatiotemporal');
        const response = await service.train({
            data: { x: [1], y: [2], z: [0], t: [1], value: [3] }
        });

        expect(response.data).toEqual({ model_id: 'm1' });
    });
});

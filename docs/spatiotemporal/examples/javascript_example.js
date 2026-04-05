const BASE = 'http://127.0.0.1:8000/api/spatiotemporal';

async function run() {
  const trainResp = await fetch(`${BASE}/train`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      data: {
        x: [120.1, 120.2, 120.3],
        y: [30.1, 30.2, 30.3],
        z: [10.0, 10.2, 10.4],
        t: [1711929600, 1712016000, 1712102400],
        value: [80.0, 82.5, 84.2]
      },
      model_type: 'nonseparable',
      options: { optimization: { method: 'mle', max_iterations: 120 } }
    })
  });
  const trainBody = await trainResp.json();
  const modelId = trainBody.data.model_id;

  const predictResp = await fetch(`${BASE}/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model_id: modelId,
      target_positions: { x: [120.4], y: [30.4], z: [10.6] },
      target_times: [1712188800],
      prediction_days: 7,
      options: { use_cache: true }
    })
  });

  console.log(await predictResp.json());
}

run().catch(console.error);

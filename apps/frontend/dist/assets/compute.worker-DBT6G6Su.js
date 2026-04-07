(function() {
	const A = /* @__PURE__ */ new Set();
	function l(e, t, s) {
		const h = {
			id: e,
			kind: "progress",
			progress: Math.max(0, Math.min(100, t)),
			message: s
		};
		self.postMessage(h);
	}
	function Y(e, t) {
		const s = {
			id: e,
			kind: "result",
			result: t
		};
		self.postMessage(s);
	}
	function v(e, t) {
		const s = {
			id: e,
			kind: "error",
			error: t instanceof Error ? t.message : String(t)
		};
		self.postMessage(s);
	}
	function E(e) {
		if (A.has(e)) throw new Error("任务已取消");
	}
	function N(e) {
		const t = typeof e == "number" ? e : Number(e);
		return Number.isFinite(t) ? t : null;
	}
	function T(e) {
		let t = Number.POSITIVE_INFINITY, s = Number.NEGATIVE_INFINITY, h = Number.POSITIVE_INFINITY, c = Number.NEGATIVE_INFINITY;
		for (const n of e) t = Math.min(t, n.x), s = Math.max(s, n.x), h = Math.min(h, n.y), c = Math.max(c, n.y);
		return {
			minX: t,
			maxX: s,
			minY: h,
			maxY: c
		};
	}
	function V(e, t) {
		const s = Array.isArray(t == null ? void 0 : t.points) ? t.points : [], h = (t == null ? void 0 : t.dedupe) !== !1, c = (t == null ? void 0 : t.normalize) === !0, n = [], o = /* @__PURE__ */ new Set();
		let u = 0;
		if (l(e, 5, "开始清洗采样点"), s.forEach((i, M) => {
			M % 200 === 0 && (E(e), l(e, Math.min(45, 5 + M / Math.max(1, s.length) * 40), "校验采样点坐标与数值"));
			const b = N(i == null ? void 0 : i.x), S = N(i == null ? void 0 : i.y), w = N(i == null ? void 0 : i.value);
			if (b === null || S === null || w === null) {
				u += 1;
				return;
			}
			const F = `${b.toFixed(6)}:${S.toFixed(6)}`;
			if (h && o.has(F)) {
				u += 1;
				return;
			}
			o.add(F), n.push({
				...i,
				x: b,
				y: S,
				value: w
			});
		}), E(e), n.length === 0) throw new Error("预处理后没有可用采样点");
		const r = n.map((i) => N(i.value)).filter((i) => i !== null), m = Math.min(...r), f = Math.max(...r), g = r.reduce((i, M) => i + M, 0) / r.length;
		if (c && f > m) for (const i of n) E(e), i.normalizedValue = ((N(i.value) || 0) - m) / (f - m);
		const x = T(n);
		return l(e, 100, "预处理完成"), {
			points: n,
			removedCount: u,
			pointCount: n.length,
			bounds: x,
			statistics: {
				minValue: m,
				maxValue: f,
				meanValue: g
			}
		};
	}
	function I(e, t) {
		var r, m, f, g;
		const s = (r = N("longitude" in e ? e.longitude : e.x)) != null ? r : 0, h = (m = N("latitude" in e ? e.latitude : e.y)) != null ? m : 0, c = (f = N("longitude" in t ? t.longitude : t.x)) != null ? f : 0, n = (g = N("latitude" in t ? t.latitude : t.y)) != null ? g : 0, o = s - c, u = h - n;
		return Math.sqrt(o * o + u * u);
	}
	function D(e, t) {
		const s = t == null ? void 0 : t.start, h = Array.isArray(t == null ? void 0 : t.waypoints) ? t.waypoints : [], c = t == null ? void 0 : t.end;
		if (!s) throw new Error("缺少路径起点");
		const n = [...h], o = [s];
		let u = s, r = 0;
		const m = Math.max(1, n.length);
		for (let f = 0; f < m && (E(e), n.length !== 0); f += 1) {
			let g = 0, x = Number.POSITIVE_INFINITY;
			for (let M = 0; M < n.length; M += 1) {
				const b = I(u, n[M]);
				b < x && (x = b, g = M);
			}
			const [i] = n.splice(g, 1);
			o.push(i), r += x, u = i, l(e, 15 + (f + 1) / m * 70, "正在计算最短访问序列");
		}
		return c && (r += I(u, c), o.push(c)), l(e, 100, "路径规划完成"), {
			route: o,
			totalDistance: r,
			estimatedDurationSeconds: Math.round(r / 12 * 3600)
		};
	}
	function C(e, t) {
		const s = Array.isArray(t == null ? void 0 : t.candidates) ? t.candidates : [], h = Array.isArray(t == null ? void 0 : t.existingPoints) ? t.existingPoints : [], c = Math.max(1, Number((t == null ? void 0 : t.count) || 10)), n = Math.max(0, Number((t == null ? void 0 : t.minDistance) || 0));
		if (s.length === 0) return {
			recommendations: [],
			requestedCount: c,
			selectedCount: 0
		};
		const o = s.map((r, m) => {
			var M;
			E(e), m % 100 === 0 && l(e, Math.min(50, m / Math.max(1, s.length) * 50), "正在评估候选采样点");
			const f = (M = N(r.uncertainty)) != null ? M : 0, g = h.length === 0 ? 1 : Math.min(...h.map((b) => I(r, b))), x = Math.min(1, g / Math.max(1, n || g)), i = f * .7 + x * .3;
			return {
				...r,
				score: i
			};
		});
		o.sort((r, m) => m.score - r.score);
		const u = [];
		for (const r of o) {
			if (E(e), u.length >= c) break;
			u.some((m) => I(m, r) < n) || u.push({
				...r,
				priority: u.length + 1
			});
		}
		return l(e, 100, "采样优化完成"), {
			recommendations: u,
			requestedCount: c,
			selectedCount: u.length
		};
	}
	function X(e, t, s, h) {
		var o, u;
		let c = 0, n = 0;
		for (const r of e) {
			const m = t - r.x, f = s - r.y, g = Math.sqrt(m * m + f * f);
			if (g === 0) return (o = r.value) != null ? o : 0;
			const x = 1 / Math.pow(g, h);
			c += ((u = r.value) != null ? u : 0) * x, n += x;
		}
		return n > 0 ? c / n : 0;
	}
	function z(e, t) {
		const s = Array.isArray(t == null ? void 0 : t.points) ? t.points : [], h = Math.max(1, Math.min(4, Number((t == null ? void 0 : t.power) || 2))), c = Math.max(10, Number((t == null ? void 0 : t.gridResolution) || 100)), n = Math.min(180, c);
		if (s.length < 3) throw new Error("预览插值至少需要 3 个采样点");
		const o = t != null && t.bounds && Number.isFinite(t.bounds.minX) ? t.bounds : T(s), u = [], r = o.maxX - o.minX || 1, m = o.maxY - o.minY || 1;
		for (let f = 0; f < n; f += 1) {
			E(e);
			const g = o.minY + f / Math.max(1, n - 1) * m;
			for (let x = 0; x < n; x += 1) {
				const i = o.minX + x / Math.max(1, n - 1) * r;
				u.push({
					x: i,
					y: g,
					value: X(s, i, g, h)
				});
			}
			l(e, Math.min(98, (f + 1) / n * 100), "正在计算插值网格");
		}
		return l(e, 100, "插值预览完成"), {
			bounds: o,
			resolution: n,
			prediction: u
		};
	}
	self.onmessage = (e) => {
		const t = e.data;
		if (!t || typeof t != "object") return;
		if (t.channel === "cancel") {
			A.add(t.id);
			return;
		}
		const { id: s, type: h, payload: c } = t;
		try {
			let n;
			switch (h) {
				case "dataPreprocess":
					n = V(s, c);
					break;
				case "samplingOptimize":
					n = C(s, c);
					break;
				case "routePlan":
					n = D(s, c);
					break;
				case "krigingPreview":
					n = z(s, c);
					break;
				default: throw new Error(`不支持的任务类型: ${String(h)}`);
			}
			Y(s, n);
		} catch (n) {
			v(s, n);
		} finally {
			A.delete(s);
		}
	};
})();

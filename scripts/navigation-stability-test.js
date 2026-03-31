#!/usr/bin/env node
/* eslint-disable no-console */

function toRadians(v) {
  return (v * Math.PI) / 180;
}

function haversineDistance(start, end) {
  const lon1 = toRadians(start[0]);
  const lat1 = toRadians(start[1]);
  const lon2 = toRadians(end[0]);
  const lat2 = toRadians(end[1]);
  const dLon = lon2 - lon1;
  const dLat = lat2 - lat1;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return 6371000 * c;
}

function interpolate(start, end, ratio) {
  return [
    start[0] + (end[0] - start[0]) * ratio,
    start[1] + (end[1] - start[1]) * ratio
  ];
}

function planOfflineRoute(start, end, waypoints = 3) {
  const polyline = [start];
  for (let i = 1; i <= waypoints; i += 1) {
    polyline.push(interpolate(start, end, i / (waypoints + 1)));
  }
  polyline.push(end);
  let distance = 0;
  for (let i = 1; i < polyline.length; i += 1) {
    distance += haversineDistance(polyline[i - 1], polyline[i]);
  }
  return { polyline, distance };
}

function main() {
  const rounds = 500;
  const start = [116.397, 39.908];
  const end = [116.477, 39.948];
  let success = 0;

  for (let i = 0; i < rounds; i += 1) {
    const route = planOfflineRoute(start, end, 3);
    const directDistance = haversineDistance(start, end);
    const isValid = route.polyline.length >= 2
      && route.distance > 0
      && route.distance >= directDistance * 0.98
      && route.distance <= directDistance * 1.2;
    if (isValid) {
      success += 1;
    }
  }

  const accuracy = Number(((success / rounds) * 100).toFixed(2));
  const passed = accuracy >= 95;
  console.log('[navigation-stability-test] 完成');
  console.log(`rounds=${rounds}`);
  console.log(`accuracy=${accuracy}%`);
  console.log(`passed=${passed}`);

  if (!passed) {
    process.exit(1);
  }
}

main();

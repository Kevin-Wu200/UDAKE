const path = require("path");

async function loadNotarizeFunction() {
  try {
    const electronNotarize = require("@electron/notarize");
    if (electronNotarize && typeof electronNotarize.notarize === "function") {
      return electronNotarize.notarize;
    }
  } catch (error) {
    // Ignore and fallback.
  }

  try {
    const electronNotarize = require("electron-notarize");
    if (electronNotarize && typeof electronNotarize.notarize === "function") {
      return electronNotarize.notarize;
    }
  } catch (error) {
    // Ignore and fallback.
  }

  return null;
}

module.exports = async function notarizeApp(context) {
  const { electronPlatformName, appOutDir, packager } = context || {};
  if (electronPlatformName !== "darwin") {
    return;
  }

  const appleId = process.env.APPLE_ID;
  const appleIdPassword = process.env.APPLE_APP_SPECIFIC_PASSWORD;
  const teamId =
    process.env.APPLE_TEAM_ID ||
    (packager && packager.info && packager.info.config.notarize
      ? packager.info.config.notarize.teamId
      : undefined);

  if (!appleId || !appleIdPassword || !teamId) {
    console.log(
      "[notarize] 未提供 APPLE_ID / APPLE_APP_SPECIFIC_PASSWORD / APPLE_TEAM_ID，跳过公证。",
    );
    return;
  }

  const notarize = await loadNotarizeFunction();
  if (!notarize) {
    console.log(
      "[notarize] 未安装 @electron/notarize 或 electron-notarize，跳过公证。",
    );
    return;
  }

  const appName = packager.appInfo.productFilename;
  const appPath = path.join(appOutDir, `${appName}.app`);
  console.log(`[notarize] 开始公证: ${appPath}`);

  await notarize({
    appBundleId: packager.appInfo.id,
    appPath,
    appleId,
    appleIdPassword,
    teamId,
  });

  console.log("[notarize] 公证提交成功。");
};

const fs = require("fs");
const path = require("path");
const { marked } = require("marked");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const LANDING_PAGE_ROOT = path.join(PROJECT_ROOT, "apps", "frontend", "landing-page");
const DOCS_ROOT = path.join(LANDING_PAGE_ROOT, "docs");
const OUTPUT_ROOT = path.join(LANDING_PAGE_ROOT, "docs-html");
const TEMPLATE_PATH = path.join(
  LANDING_PAGE_ROOT,
  "templates",
  "docs-template.html",
);

const FEATURE_DETAIL_PAGE_MAP = {
  interpolation: "pages/interpolation.html",
  uncertainty: "pages/uncertainty.html",
  sampling: "pages/sampling.html",
  optimization: "pages/optimization.html",
  realtime: "pages/realtime.html",
  deepLearning: "pages/deepLearning.html",
  anomaly: "pages/anomaly.html",
  risk: "pages/risk.html",
};

const WATCH_MODE = process.argv.includes("--watch");

marked.setOptions({
  gfm: true,
});

function toPosix(filePath) {
  return filePath.split(path.sep).join("/");
}

function ensureDirectory(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function cleanOutputDirectory() {
  fs.rmSync(OUTPUT_ROOT, { recursive: true, force: true });
  ensureDirectory(OUTPUT_ROOT);
}

function getMarkdownFiles(dirPath) {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  return entries
    .flatMap((entry) => {
      const fullPath = path.join(dirPath, entry.name);
      if (entry.isDirectory()) {
        return getMarkdownFiles(fullPath);
      }
      if (entry.isFile() && entry.name.toLowerCase().endsWith(".md")) {
        return [fullPath];
      }
      return [];
    })
    .sort();
}

function splitLinkTarget(target) {
  const match = target.match(/^([^?#]*)(\?[^#]*)?(#.*)?$/);
  return {
    pathname: match ? match[1] : target,
    search: match && match[2] ? match[2] : "",
    hash: match && match[3] ? match[3] : "",
  };
}

function isExternalTarget(target) {
  return (
    !target ||
    target.startsWith("#") ||
    target.startsWith("//") ||
    /^[a-zA-Z][a-zA-Z\d+.-]*:/.test(target)
  );
}

function rewriteRelativeTarget(target, sourceFile, outputFile) {
  if (isExternalTarget(target)) {
    return target;
  }

  const { pathname, search, hash } = splitLinkTarget(target);
  if (!pathname) {
    return target;
  }

  const resolvedSourcePath = path.resolve(path.dirname(sourceFile), pathname);
  const relativeToDocs = path.relative(DOCS_ROOT, resolvedSourcePath);
  if (relativeToDocs.startsWith("..")) {
    return target;
  }

  let outputTargetPath;
  if (pathname.toLowerCase().endsWith(".md")) {
    outputTargetPath = path.join(
      OUTPUT_ROOT,
      relativeToDocs.replace(/\.md$/i, ".html"),
    );
  } else {
    outputTargetPath = path.join(DOCS_ROOT, relativeToDocs);
  }

  const relativeOutputTarget = path.relative(
    path.dirname(outputFile),
    outputTargetPath,
  );
  const normalizedTarget = toPosix(relativeOutputTarget || ".");
  return `${normalizedTarget}${search}${hash}`;
}

function slugify(text, seenSlugs) {
  const base = text
    .toLowerCase()
    .trim()
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");

  const slugBase = base || "section";
  const seenCount = seenSlugs.get(slugBase) || 0;
  seenSlugs.set(slugBase, seenCount + 1);
  return seenCount === 0 ? slugBase : `${slugBase}-${seenCount + 1}`;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;");
}

function renderToc(headings) {
  const tocItems = headings
    .filter((heading) => heading.depth >= 2 && heading.depth <= 3)
    .map((heading) => {
      const itemClass =
        heading.depth === 3 ? "docs-toc-item docs-toc-item-sub" : "docs-toc-item";
      return `<li class="${itemClass}"><a href="#${heading.slug}">${escapeHtml(
        heading.text,
      )}</a></li>`;
    })
    .join("");

  if (!tocItems) {
    return '<li class="docs-toc-item docs-toc-item-empty">当前文档暂无目录</li>';
  }

  return tocItems;
}

function getFeatureBackHref(relativeDocPath, rootPrefix) {
  const featureKey = relativeDocPath.replace(/\.md$/i, "").replace(/\\/g, "/");
  const detailPage = FEATURE_DETAIL_PAGE_MAP[featureKey];
  if (!detailPage) {
    return `${rootPrefix}index.html#features`;
  }
  return `${rootPrefix}${detailPage}`;
}

function createRenderer(sourceFile, outputFile, headings) {
  const seenSlugs = new Map();
  const renderer = new marked.Renderer();

  renderer.heading = function heading(token) {
    const text = this.parser.parseInline(token.tokens);
    const plainText = token.text || text.replace(/<[^>]+>/g, "").trim();
    const slug = slugify(plainText, seenSlugs);
    headings.push({
      depth: token.depth,
      slug,
      text: plainText,
    });

    return `<h${token.depth} id="${slug}">${text}</h${token.depth}>\n`;
  };

  renderer.link = function link(token) {
    const href = rewriteRelativeTarget(token.href, sourceFile, outputFile);
    const text = this.parser.parseInline(token.tokens);
    const title = token.title ? ` title="${escapeHtml(token.title)}"` : "";
    return `<a href="${escapeHtml(href)}"${title}>${text}</a>`;
  };

  renderer.image = function image(token) {
    const href = rewriteRelativeTarget(token.href, sourceFile, outputFile);
    const alt = token.text ? escapeHtml(token.text) : "";
    const title = token.title ? ` title="${escapeHtml(token.title)}"` : "";
    return `<img src="${escapeHtml(href)}" alt="${alt}" loading="lazy"${title}>`;
  };

  return renderer;
}

function buildDocument(filePath, template) {
  const relativeDocPath = path.relative(DOCS_ROOT, filePath);
  const outputFile = path.join(
    OUTPUT_ROOT,
    relativeDocPath.replace(/\.md$/i, ".html"),
  );
  const outputDir = path.dirname(outputFile);
  const rootPrefix = `${toPosix(path.relative(outputDir, LANDING_PAGE_ROOT)) || "."}/`;
  const relativeDocLabel = toPosix(relativeDocPath);
  const markdown = fs.readFileSync(filePath, "utf8");
  const headings = [];
  const renderer = createRenderer(filePath, outputFile, headings);
  const contentHtml = marked.parse(markdown, { renderer });
  const titleHeading = headings.find((heading) => heading.depth === 1);
  const pageTitle = titleHeading
    ? titleHeading.text
    : path.basename(filePath, path.extname(filePath));
  const tocHtml = renderToc(headings);
  const featureBackHref = getFeatureBackHref(relativeDocPath, rootPrefix);
  const html = template
    .replaceAll("{{pageTitle}}", escapeHtml(pageTitle))
    .replaceAll("{{relativeDocLabel}}", escapeHtml(relativeDocLabel))
    .replaceAll("{{rootPrefix}}", rootPrefix)
    .replaceAll("{{featureBackHref}}", featureBackHref)
    .replaceAll("{{toc}}", tocHtml)
    .replaceAll("{{content}}", contentHtml);

  ensureDirectory(outputDir);
  fs.writeFileSync(outputFile, html, "utf8");
  return outputFile;
}

function buildAllDocs() {
  if (!fs.existsSync(DOCS_ROOT)) {
    throw new Error(`未找到文档目录: ${DOCS_ROOT}`);
  }

  const template = fs.readFileSync(TEMPLATE_PATH, "utf8");
  cleanOutputDirectory();
  const markdownFiles = getMarkdownFiles(DOCS_ROOT);
  const generatedFiles = markdownFiles.map((filePath) =>
    buildDocument(filePath, template),
  );

  console.log(
    `[md-to-html] 已生成 ${generatedFiles.length} 个 HTML 文档到 ${OUTPUT_ROOT}`,
  );
}

function startWatchMode() {
  let timer = null;
  const rebuild = () => {
    try {
      buildAllDocs();
    } catch (error) {
      console.error("[md-to-html] 构建失败:", error.message);
    }
  };

  rebuild();
  console.log(`[md-to-html] 监听中: ${DOCS_ROOT}`);

  fs.watch(DOCS_ROOT, { recursive: true }, () => {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(rebuild, 150);
  });
}

if (WATCH_MODE) {
  startWatchMode();
} else {
  buildAllDocs();
}

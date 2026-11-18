// Random: goes straight to one of the addresses listed on the page, never the one the visitor came
// from. It runs in the head of a bare page, right after a meta tag holding the list, so the jump
// happens before anything is drawn. A file, not inline code, so a strict Content-Security-Policy
// allows it. The page visited before is read from a same-site referrer rather than the address, so
// every Random link is the same address and the browser keeps one copy of the list.

// The referrer's address, still percent-encoded, when the referrer is this site's page right under
// `home` (/a/ under /); otherwise '', which excludes nothing.
function referrerAddress(referrer, origin, home) {
  let path;
  try {
    const url = new URL(referrer);
    if (url.origin !== origin) return '';
    path = url.pathname;
  } catch {
    return ''; // No referrer, or one that is no address.
  }
  if (!path.startsWith(home)) return '';
  return /^[^/]+\/$/u.test(path.slice(home.length)) ? path.slice(home.length, -1) : '';
}

// Equal odds over `addresses` without `from` (percent-encoded); malformed encoding excludes nothing.
// null when nothing is left.
function randomAddress(addresses, from = '', random = Math.random) {
  let current = '';
  try {
    current = decodeURIComponent(from).normalize('NFC');
  } catch (error) {
    if (!(error instanceof URIError)) throw error;
  }
  const candidates = addresses.filter(address => address.normalize('NFC') !== current);
  if (!candidates.length) return null;
  return candidates[Math.floor(random() * candidates.length)];
}

const meta = document.querySelector('meta[name="random-addresses"]');
const home = meta.dataset.home;
const address = randomAddress(JSON.parse(meta.content), referrerAddress(document.referrer, location.origin, home));
// The destination comes from the list alone: every address sits right under home.
location.replace(address ? `${home}${encodeURIComponent(address)}/` : home);

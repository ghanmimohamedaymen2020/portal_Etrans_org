(function () {
  const root = window.appI18n || {};
  const lang = root.lang || document.documentElement.lang || 'fr';
  const translations = root.translations || {};

  function translateText(text) {
    if (!text || lang === 'fr') return text;
    const trimmed = text.trim();
    if (!trimmed) return text;

    const direct = translations[trimmed];
    if (direct) {
      return text.replace(trimmed, direct);
    }

    let output = text;
    output = output.replace(/Bonjour/g, 'Hello');
    output = output.replace(/Dashboard Administrateur/g, 'Administrator Dashboard');
    output = output.replace(/Dashboard Management/g, 'Management Dashboard');
    output = output.replace(/GESTION DES ROUTING TGY TUNISIE/g, 'TGY Tunisia Routing Management');
    output = output.replace(/Retour au dashboard/g, 'Back to dashboard');
    output = output.replace(/Réinitialiser/g, 'Reset');
    output = output.replace(/Enregistrer/g, 'Save');
    output = output.replace(/Annuler/g, 'Cancel');
    output = output.replace(/Chargement…|Chargement\.\.\./g, 'Loading...');
    output = output.replace(/Précédent/g, 'Previous');
    output = output.replace(/Suivant/g, 'Next');
    output = output.replace(/Colonnes/g, 'Columns');
    output = output.replace(/Rechercher\.\.\./g, 'Search...');
    output = output.replace(/Liste des REF en doublon/g, 'List of duplicate REF values');
    output = output.replace(/Ligne (\d+)/g, 'Row $1');
    output = output.replace(/Erreur import/g, 'Import error');
    output = output.replace(/Erreur serveur/g, 'Server error');
    output = output.replace(/Page non trouvée/g, 'Page not found');
    output = output.replace(/Système opérationnel/g, 'System operational');
    output = output.replace(/Connexion en cours\.\.\./g, 'Signing in...');
    output = output.replace(/Réinitialisation en cours\.\.\./g, 'Resetting...');
    output = output.replace(/Envoi en cours\.\.\./g, 'Sending...');
    output = output.replace(/Modification en cours\.\.\./g, 'Updating...');
    output = output.replace(/Force du mot de passe : faible/g, 'Password strength: weak');
    output = output.replace(/Force du mot de passe : moyenne/g, 'Password strength: fair');
    output = output.replace(/Force du mot de passe : bonne/g, 'Password strength: good');
    output = output.replace(/Force du mot de passe : excellente/g, 'Password strength: excellent');
    output = output.replace(/✓ Les mots de passe correspondent/g, '✓ Passwords match');
    output = output.replace(/✗ Les mots de passe ne correspondent pas/g, '✗ Passwords do not match');
    output = output.replace(/Rows shown on page:/g, 'Rows shown on page:');
    output = output.replace(/Nbr ligne affiché sur la page:/g, 'Rows shown on page:');
    return output;
  }

  function translateAttributes(node) {
    ['placeholder', 'title', 'aria-label'].forEach((attr) => {
      if (node.hasAttribute && node.hasAttribute(attr)) {
        const value = node.getAttribute(attr);
        const translated = translateText(value);
        if (translated !== value) node.setAttribute(attr, translated);
      }
    });
    if (node.tagName === 'INPUT' && (node.type === 'button' || node.type === 'submit')) {
      const value = node.value;
      const translated = translateText(value);
      if (translated !== value) node.value = translated;
    }
  }

  // Returns true when a node lives inside a <td> data cell (DB values — must not be translated).
  function isInsideDataCell(node) {
    let el = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
    while (el && el !== document.body) {
      if (el.tagName === 'TD') return true;
      el = el.parentElement;
    }
    return false;
  }

  function translateNode(node) {
    if (lang === 'fr' || !node) return;
    if (node.nodeType === Node.TEXT_NODE) {
      if (isInsideDataCell(node)) return;
      const translated = translateText(node.textContent);
      if (translated !== node.textContent) node.textContent = translated;
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    translateAttributes(node);
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        return isInsideDataCell(n) ? NodeFilter.FILTER_SKIP : NodeFilter.FILTER_ACCEPT;
      },
    });
    let current;
    while ((current = walker.nextNode())) {
      const translated = translateText(current.textContent);
      if (translated !== current.textContent) current.textContent = translated;
    }
    node.querySelectorAll('*').forEach(translateAttributes);
  }

  function patchDialogFunction(name) {
    const original = window[name];
    if (typeof original !== 'function') return;
    window[name] = function patched(message) {
      const args = Array.from(arguments);
      if (typeof args[0] === 'string') {
        args[0] = translateText(args[0]);
      }
      return original.apply(window, args);
    };
  }

  function observeMutations() {
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        mutation.addedNodes.forEach((node) => translateNode(node));
        if (mutation.type === 'characterData' && mutation.target) {
          translateNode(mutation.target);
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  function boot() {
    if (lang === 'fr') return;
    document.title = translateText(document.title);
    translateNode(document.body);
    patchDialogFunction('alert');
    patchDialogFunction('confirm');
    observeMutations();
  }

  window.appI18n = Object.assign(root, {
    t: translateText,
    locale: lang === 'en' ? 'en-US' : 'fr-FR',
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
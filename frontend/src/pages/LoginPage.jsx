import { useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import keymanageLogo from "../assets/keymanage-ai-robot-logo-transparent.png";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [helpMessage, setHelpMessage] = useState("");

  const handleSubmit = (event) => {
    event.preventDefault();
    setErrorMessage("");
    setHelpMessage("");
    const result = login(email, password, rememberMe);
    if (!result.success) setErrorMessage(result.message);
  };

  return (
    <main className="login-page min-h-screen w-full grid grid-cols-1 lg:grid-cols-2 bg-slate-950 text-slate-100 overflow-hidden">
      <section className="login-brand-panel" aria-label="Présentation de KeyManage AI">
        <span className="login-glow login-glow-one" />
        <span className="login-glow login-glow-two" />

        <div className="login-brand-content">
          <header className="login-brand-header">
            <span className="login-logo-shell">
              <img src={keymanageLogo} alt="" aria-hidden="true" />
            </span>
            <div>
              <strong>KeyManage AI</strong>
              <span>Accounting Engine</span>
            </div>
          </header>

          <div className="login-hero-copy">
            <span className="login-kicker"><Sparkles size={14} /> Comptabilité augmentée par l’IA</span>
            <h1>Votre plateforme intelligente au service de la comptabilité.</h1>
            <p>Automatisez la lecture, le contrôle et l’imputation de vos factures avec une supervision humaine à chaque étape clé.</p>
          </div>

          <div className="login-feature-chips" aria-label="Fonctionnalités principales">
            <span>Extraction IA</span>
            <span>Validation supervisée</span>
            <span>Mémoire IA</span>
          </div>

          <div className="login-dashboard-mockup">
            <div className="login-mockup-topbar">
              <span><i /><i /><i /></span>
              <b>Vue d’ensemble</b>
              <small>Temps réel</small>
            </div>
            <div className="login-mockup-metrics">
              <article>
                <span>Factures traitées</span>
                <strong>2 486</strong>
                <small>+18,4 % ce mois</small>
              </article>
              <article>
                <span>Taux de précision</span>
                <strong>99,8 %</strong>
                <small>Contrôle supervisé</small>
              </article>
              <article>
                <span>Gain de temps</span>
                <strong>80 %</strong>
                <small>Sur chaque dossier</small>
              </article>
            </div>
            <div className="login-mockup-table">
              <div className="login-mockup-row login-mockup-row-head"><span>Fournisseur</span><span>Compte</span><span>Statut</span></div>
              <div className="login-mockup-row"><span><i className="login-company-dot blue" /> ORANGE</span><b>626</b><em className="success">Comptabilisée</em></div>
              <div className="login-mockup-row"><span><i className="login-company-dot violet" /> METRO FRANCE</span><b>6063</b><em className="review">À contrôler</em></div>
              <div className="login-mockup-row"><span><i className="login-company-dot cyan" /> BOUYGUES TELECOM</span><b>626</b><em className="success">Validée</em></div>
            </div>
          </div>

          <blockquote className="login-testimonial">
            <div className="login-stars" aria-label="5 étoiles">★★★★★</div>
            <p>« Gagnez jusqu’à 80 % de temps sur le traitement des pièces comptables. »</p>
            <footer><span>EC</span><div><strong>Cabinet partenaire</strong><small>Expertise comptable & conseil</small></div></footer>
          </blockquote>
        </div>
      </section>

      <section className="login-form-panel">
        <div className="login-form-card">
          <div className="login-form-heading">
            <span className="login-secure-label"><ShieldCheck size={15} /> Espace sécurisé</span>
            <h2>Connexion</h2>
            <p>Accédez à votre environnement KeyManage AI.</p>
          </div>

          <div className="login-active-profile">
            <span className="login-profile-avatar">EC</span>
            <div><strong>Expert Comptable</strong><small>Expert-comptable</small></div>
            <span className="login-profile-status"><i /> Accès sécurisé</span>
          </div>

          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <label>
              <span>Adresse e-mail</span>
              <div className="login-input-shell">
                <Mail size={18} aria-hidden="true" />
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="expert@keymanage.ai"
                  autoComplete="email"
                  required
                />
              </div>
            </label>

            <label>
              <span>Mot de passe</span>
              <div className="login-input-shell">
                <LockKeyhole size={18} aria-hidden="true" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Votre mot de passe"
                  autoComplete="current-password"
                  required
                />
                <button type="button" className="login-password-toggle" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}>
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>

            <div className="login-options">
              <label className="login-remember">
                <input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} />
                <span>Se souvenir de moi</span>
              </label>
              <button type="button" onClick={() => setHelpMessage("Veuillez contacter votre administrateur système.")}>Mot de passe oublié ?</button>
            </div>

            {helpMessage ? <div className="login-help-message" role="status"><CheckCircle2 size={16} /> {helpMessage}</div> : null}
            {errorMessage ? <div className="login-error-message" role="alert">{errorMessage}</div> : null}

            <button type="submit" className="login-submit-button">
              Se connecter <ArrowRight size={18} />
            </button>
          </form>

          <div className="login-form-footer">
            <ShieldCheck size={15} /> Connexion protégée · Données comptables confidentielles
          </div>
        </div>
      </section>
    </main>
  );
}

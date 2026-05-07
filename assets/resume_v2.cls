%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Resume v2 class overrides
% Keeps base resume.cls intact and only overrides
% work-experience subsection formatting.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{resume_v2}[2026/05/05 v2.3 Resume class overrides for template v2]

\LoadClass{resume}
\IfFileExists{libertinus.sty}{%
  \RequirePackage{libertinus}%
}{%
  \RequirePackage{mathdesign} % acceptable fallback serif
}
\RequirePackage{tabularx}

\renewenvironment{myrSubsection}[3]{
  \vspace{3pt}  % Between job entries: reduced from 16pt
  \noindent
  \begin{tabularx}{\linewidth}{@{}X r@{}}
    {\bfseries #3} & {\normalsize #2} \\[0.2em]  % More space between title+date and company line
  \end{tabularx}
  % #1\\[0.1em]  % Company to bullets: reduced from 0.5em
  #1\par\vspace{-0.4em}
  \begin{list}{$\bullet$}{
    \leftmargin=1.5em   % Hanging indent
    \itemsep 0.2em      % Between bullets
    \topsep 0em
    \parsep 0em
    \partopsep 0em
  }
}{
  \end{list}
  \vspace{3pt}  % Between job entries: reduced from 16pt
}

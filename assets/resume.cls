%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Medium Length Professional CV - RESUME CLASS FILE
%
% This template has been downloaded from:
% http://www.LaTeXTemplates.com
%
% This class file defines the structure and design of the template. 
%
% Original header:
% Copyright (C) 2010 by Trey Hunner
%
% Copying and distribution of this file, with or without modification,
% are permitted in any medium without royalty provided the copyright
% notice and this notice are preserved. This file is offered as-is,
% without any warranty.
%
% Created by Trey Hunner and modified by www.LaTeXTemplates.com
%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

\ProvidesClass{resume}[2024/10/20 v1.9 Resume class]

\LoadClass[09pt,letterpaper]{article} % Font size and paper type

\usepackage[parfill]{parskip} % Remove paragraph indentation
\usepackage{array} % Required for boldface (\bf and \bfseries) tabular columns
\usepackage{tabularx}
\usepackage{ifthen} % Required for ifthenelse statements
\usepackage{graphicx}

\usepackage{tikz}

\pagestyle{empty} % Suppress page numbers

\usepackage{xcolor}
\definecolor{purplea}{RGB}{162, 139, 186}
\definecolor{purpleb}{RGB}{184, 184, 220}
\definecolor{mygray}{RGB}{243,243,243}
\definecolor{bluegrapy}{RGB}{193,207,232}
\definecolor{bluelighta}{RGB}{193,207,232}

\definecolor{bluedark}{RGB}{18,54,147}
\definecolor{bluelight}{RGB}{0,83,214}

%----------------------------------------------------------------------------------------
%	HEADINGS COMMANDS: Commands for printing name and address
%----------------------------------------------------------------------------------------

\def \name#1{\def\@name{#1}} % Defines the \name command to set name
\def \@name {} % Sets \@name to empty by default

\def \myaddress#1#2{
  \@ifundefined{@addressone}{
    \def \@addressone{#1 & #2 }
  }{
  \@ifundefined{@addresstwo}{
    \def \@addresstwo{#1 &  #2}
  }{
  \@ifundefined{@addressthree}{
    \def \@addressthree{#1 &  #2}
  }{
  \@ifundefined{@addressfour}{
    \def \@addressfour{ #1 &  #2 }
  }{
  \def \@addressfive{#1 & #2}
  }
  }}
  }
}

\def \printpicture #1{
 \includegraphics[width=3cm]{my_pic.jpeg}
}


% The heading below prints \@name with the contact rows and photo; the
% section environments after it own the CV body layout.


% Name/address block on the left, photo top-aligned on the right. Address
% rows are two-column tabular fragments (icon & text), so they need the inner
% tabular below. Plain side-by-side minipages with explicit widths keep the
% layout deterministic: no trial-pass measuring, no overlap. Paragraph indent
% is zeroed inside the block so icon rows and the photo align to the margins.
\let\ori@document=\document
\renewcommand{\document}{
  \ori@document  % Begin document

 \setlength{\leftmargin}{2.0em} % Margin within the section

\vspace{0.0cm}
\noindent\setlength{\parindent}{0pt}
\begin{minipage}[t]{\dimexpr\linewidth-4.2cm\relax}
  {\scshape {\namesize \@name}}\par\nameskip
  \begin{tabular}{@{}ll@{}}
    \@addressone \\
    \@addresstwo \\
    \@addressthree \\
    \@addressfour \\
  \end{tabular}
\end{minipage}%
\hfill%
\begin{minipage}[t]{3.0cm}\raggedleft \printpicture{}\end{minipage}

}

%----------------------------------------------------------------------------------------
%	SECTION FORMATTING
%----------------------------------------------------------------------------------------

% Defines the rSection environment for the large sections within the CV
% Section titles use non-bold small caps: Latin Modern has no bold small-caps
% shape, so \textbf here only produced substitution warnings.
\newenvironment{rSection}[1]{ % 1 input argument - section name
  \sectionskip
  {\Large{\textsc{{#1}}}}
  \sectionlineskip
  \hrule % Horizontal line
  \begin{list}{}{ % List for each individual item in the section
     \setlength{\leftmargin}{1.0em} % Margin within the section
     \setlength{\rightmargin}{1.0em} % Margin within the section
  }
  \item[]
}{
  \end{list}
  \vspace{0.25cm}
}

%----------------------------------------------------------------------------------------
%	WORK EXPERIENCE FORMATTING
%----------------------------------------------------------------------------------------

\newenvironment{myrSubsection}[3]{
   \begin{tabular}{p{0.2\linewidth} p{0.76\linewidth}}

   \textsc{#2}\hfill   & {\bf{#1} }  #3 \vspace{0.3cm} \\
      &

\def\arraystretch{1.3}
      % @{} drops this table's own column padding: p{1.0\linewidth} already
      % accounts for the full column, so the padding would stick 12pt out.
      \begin{tabular}{@{}p{\linewidth}@{}}
    \begin{list}{$\cdot$}{\leftmargin=.75em \rightmargin=0cm} % \cdot used for bullets, no indentation
    \itemsep 0.5em \vspace{-1.75em} % Compress items in list together for aesthetics
     
}{
    \end{list}
    \end{tabular} 
  \end{tabular}
  \vspace{-1.0em}
}

\newenvironment{myrSubsectionEmpty2}[3]{
  \begin{tabular}{p{0.2\linewidth} p{0.76\linewidth}}
  \hfill \textsc{#2}   & {\bf{ #1} }\\
                       & {#3 \vspace{0.3cm}}\\ %&  \em {#4} \vspace{0.4cm}\\ 
    \begin{tabular}{l}
      \end{tabular} & 

\def\arraystretch{1.3}
      \begin{tabular}{p{0.70\textwidth}}
    \vspace{-1.0em} % Compress items in list together for aesthetics
}{
    \end{tabular} 
  \end{tabular}
  \vspace{0.0em}
}

\newenvironment{rSubsection}[4]{ % 4 input arguments - company name, year(s) employed, job title and location
 {\bf #1} \hfill {#2} % Bold company name and date on the right
 \ifthenelse{\equal{#3}{}}{}{ % If the third argument is not specified, don't print the job title and location line
  \\
  {\em #3} \hfill {\em #4} % Italic job title and location
  }\smallskip
  \begin{list}{$\cdot$}{\leftmargin=1em} % \cdot used for bullets, no indentation
   \itemsep -0.5em \vspace{-0.5em} % Compress items in list together for aesthetics
  }{
  \end{list}
  \vspace{0.5em} % Some space after the list of bullet points
}

% The below commands define the whitespace after certain things in the document - they can be \sduring mallskip, \medskip or \bigskip
\def\namesize{\huge} % Size of the name at the top of the document
\def\addressskip{\smallskip} % The space between the two address (or phone/email) lines
\def\sectionlineskip{\medskip} % The space above the horizontal line for each section 
\def\nameskip{\bigskip} % The space after your name at the top
\def\sectionskip{\medskip} % The space after the heading section

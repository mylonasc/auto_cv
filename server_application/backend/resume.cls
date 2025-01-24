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
\usepackage{multirow}
\usepackage{tabularx}
\usepackage{ifthen} % Required for ifthenelse statements
\usepackage{graphicx}

\usepackage{tikz}
%\usepackage{minipage}

\pagestyle{empty} % Suppress page numbers

\usepackage{xcolor}
\definecolor{purplea}{RGB}{162, 139, 186}
\definecolor{purpleb}{RGB}{184, 184, 220}
\definecolor{mygray}{RGB}{243,243,243}
\definecolor{bluegrapy}{RGB}{193,207,232}
\definecolor{bluelighta}{RGB}{193,207,232}

\definecolor{bluedark}{RGB}{18,54,147}
\definecolor{bluelight}{RGB}{0,83,214}

\usetikzlibrary{backgrounds}

%----------------------------------------------------------------------------------------
%	HEADINGS COMMANDS: Commands for printing name and address
%----------------------------------------------------------------------------------------

\def \name#1{\def\@name{#1}} % Defines the \name command to set name
\def \@name {} % Sets \@name to empty by default

\def \addressSep {$\diamond$} % Set default address separator to a diamond

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

% \printaddress is used to style an address line (given as input)
% \def \printaddress #1{
% \break
%   \begingroup
    %\def \\ {\addressSep\ }
%   \hspace{0.1cm} #1
%   \endgroup
%   \par
%   \addressskip
% }


\def \printpicture #1{
 \includegraphics[width=3cm]{my_pic.jpeg}
}


% \printname is used to print the name as a page header
\def \printname {
  %\begingroup
  %  \hfil{\MakeUppercase{\namesize\bf \@name}}\hfil
  %  \nameskip\break
  %\endgroup
{\scshape {\namesize \@name}} \hfill %{\namesize\bf \MakeUppercase \@name}\hfill
\nameskip\break
}

%----------------------------------------------------------------------------------------
%	PRINT THE HEADING LINES
%----------------------------------------------------------------------------------------


\let\ori@document=\document
\renewcommand{\document}{
  \ori@document  % Begin document

 \setlength{\leftmargin}{2.0em} % Margin within the section

%\nameskip
\vspace{0.0cm}
\begin{tabularx}{\linewidth}{c c  l  c   c  l r }
   \multicolumn{6}{ l}{
    {\scshape {\namesize \@name}} \hfill %{\namesize\bf \MakeUppercase \@name}\hfill
    \nameskip
  }  \multirow{3}{*}{ \hspace{6.0cm} \printpicture} \\
  & \@addressone & \,&  &  \\
  &  \@addresstwo \\
  &  \@addressthree & \, & &  \\
  & \@addressfour \\
  
 \end{tabularx}

}
%\printpicture

%----------------------------------------------------------------------------------------
%	SECTION FORMATTING
%----------------------------------------------------------------------------------------

% Defines the rSection environment for the large sections within the CV
\newenvironment{rSection}[1]{ % 1 input argument - section name
  \sectionskip
  % \MakeUppercase{\bf #1} % Section title
  {\Large{\textsc{ \textbf{{#1}}}}}
  \sectionlineskip
  \hrule % Horizontal line
  \begin{list}{}{ % List for each individual item in the section
     \setlength{\leftmargin}{1.0em} % Margin within the section
     \setlength{\rightmargin}{1.0em} % Margin within the section
     %\setlength{\rightmargin}{1.5em} % Margin within the section
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
      \begin{tabular}{p{1.0\linewidth}}
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

\newenvironment{myrSubsectionEmpty}[3]{
  \begin{tabular}{p{0.2\textwidth}|p{0.75\textwidth}}
    \textsc{#2}   & \bf{ #1}\\
      &   {#3 \vspace{0.3cm}} %&  \em {#4} \vspace{0.4cm}\\ 
    %\begin{tabular}{l}
    %  \end{tabular} 
  \end{tabular}
    }{}

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

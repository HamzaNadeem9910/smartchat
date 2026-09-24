# SaaS Chatbot Landing Page

A modern, responsive landing page for a SaaS chatbot application built with React, TypeScript, and Tailwind CSS.

## Prerequisites

Before running this project, make sure you have the following installed on your system:

- **Node.js** (version 18 or higher) - [Download here](https://nodejs.org/)
- **npm** (comes with Node.js) or **yarn**
- **Visual Studio Code** - [Download here](https://code.visualstudio.com/)

## Getting Started

Follow these steps to run the project on your local machine:

### 1. Clone or Download the Project

If you haven't already, download or clone this project to your local machine.

### 2. Open in Visual Studio Code

```bash
# Navigate to the project directory
cd your-project-folder

# Open in VS Code
code .
```

### 3. Install Dependencies

Open the integrated terminal in VS Code (`Ctrl+`` ` or `View > Terminal`) and run:

```bash
# Install all dependencies
npm install
```

If you encounter any issues, try clearing the npm cache first:

```bash
# Clear npm cache
npm cache clean --force

# Then install dependencies
npm install
```

### 4. Start the Development Server

```bash
# Start the development server
npm run dev
```

The application will be available at `http://localhost:5173`

## Recommended VS Code Extensions

Install these extensions for the best development experience:

1. **ES7+ React/Redux/React-Native snippets** - Provides useful React snippets
2. **Tailwind CSS IntelliSense** - Autocomplete for Tailwind classes
3. **TypeScript Importer** - Auto import for TypeScript
4. **Prettier - Code formatter** - Code formatting
5. **Auto Rename Tag** - Automatically rename paired HTML tags
6. **Bracket Pair Colorizer** - Color matching brackets
7. **GitLens** - Enhanced Git capabilities

## Project Structure

```
src/
├── components/          # Reusable components
│   ├── Header.tsx      # Navigation header
│   └── Footer.tsx      # Site footer
├── pages/              # Page components
│   ├── HomePage.tsx    # Main landing page
│   └── PricingPage.tsx # Pricing page
├── App.tsx             # Main app component (legacy)
├── main.tsx            # Application entry point
└── index.css           # Global styles and Tailwind imports
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Troubleshooting

### Common Issues and Solutions

#### 1. "Module not found" errors
```bash
# Delete node_modules and package-lock.json, then reinstall
rm -rf node_modules package-lock.json
npm install
```

#### 2. TypeScript errors
Make sure you have the TypeScript extension installed in VS Code and restart the TypeScript server:
- Press `Ctrl+Shift+P`
- Type "TypeScript: Restart TS Server"
- Press Enter

#### 3. Tailwind CSS not working
Ensure your `tailwind.config.js` and `postcss.config.js` files are properly configured and restart the dev server.

#### 4. Port already in use
If port 5173 is already in use, Vite will automatically use the next available port. Check the terminal output for the correct URL.

#### 5. ESLint errors
You can disable ESLint temporarily by adding this to your VS Code settings:
```json
{
  "eslint.enable": false
}
```

## Dependencies

This project uses the following main dependencies:

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **React Router DOM** - Client-side routing
- **Lucide React** - Icon library

## Building for Production

To create a production build:

```bash
npm run build
```

The built files will be in the `dist` folder, ready for deployment.

## Deployment

This project can be deployed to various platforms:

- **Netlify** - Drag and drop the `dist` folder
- **Vercel** - Connect your Git repository
- **GitHub Pages** - Use GitHub Actions
- **Any static hosting service**

## Support

If you encounter any issues:

1. Check that all dependencies are installed correctly
2. Ensure you're using Node.js version 18 or higher
3. Try deleting `node_modules` and reinstalling
4. Check the browser console for any runtime errors
5. Verify that all required VS Code extensions are installed

## License

This project is for educational/demonstration purposes.
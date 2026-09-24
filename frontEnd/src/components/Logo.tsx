import React from 'react';
import { Link } from 'react-router-dom';
import { MessageCircle } from 'lucide-react';

interface Props {
  className?: string;
  showText?: boolean;
}

export default function Logo({ className = '', showText = true }: Props) {
  return (
    <Link to="/" className={`flex items-center ${showText ? 'space-x-2' : ''} ${className}`}>
      <div className="w-8 h-8 bg-black rounded-md flex items-center justify-center">
        <MessageCircle className="w-5 h-5 text-white" />
      </div>
      {showText && <span className="text-xl font-semibold text-gray-900">SmartChat</span>}
    </Link>
  );
}
